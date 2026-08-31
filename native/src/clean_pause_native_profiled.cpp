#include "kcd2_runtime_profile.h"

// Keep the mature Clean Pause implementation intact while replacing only its
// bootstrap/runtime-discovery boundary. The original scanner is retained solely
// behind an explicit locator strategy used by the exact retail-validated Xbox /
// Microsoft Store 1.5.6 build. Storefront identity itself never selects runtime
// behavior; the matched BuildProfile chooses an ABI and a locator independently.
#define Start LegacyStart_Unreachable
#define Stop LegacyStop_Unreachable
#define BootstrapThread LegacyBootstrapThread_Unreachable
#define FindRuntimeEnvironment LegacyFindRuntimeEnvironment_Xbox156Only
#include "clean_pause_native.cpp"
#undef FindRuntimeEnvironment
#undef BootstrapThread
#undef Stop
#undef Start

namespace clean_pause {
namespace {

bool ThreadBelongsToCurrentProcess(DWORD threadId)
{
    if (!threadId)
        return false;

    HANDLE thread = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, threadId);
    if (!thread)
        return false;
    const DWORD ownerProcess = GetProcessIdOfThread(thread);
    CloseHandle(thread);
    return ownerProcess != 0 && ownerProcess == GetCurrentProcessId();
}

bool ValidateGameAndFrameworkIdentity(const RuntimeEnvironment& environment)
{
    if (!environment.game || !environment.system)
        return false;

    using GetGameNameFn = const char*(__fastcall*)(void*);
    if (!ValidateObjectVtable(environment.game, {
            kGameGetNameSlot,
            kGameGetFrameworkSlot }))
        return false;

    const auto getName = VFunc<GetGameNameFn>(environment.game, kGameGetNameSlot);
    const char* gameName{};
    bool nameMatches{};
    __try {
        gameName = getName ? getName(environment.game) : nullptr;
        nameMatches = gameName && std::strcmp(gameName, "kcd2") == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        nameMatches = false;
    }
    if (!nameMatches)
        return false;

    const auto getFramework = VFunc<GetGameFrameworkFn>(
        environment.game, kGameGetFrameworkSlot);
    if (!getFramework || !IsExecutable(reinterpret_cast<void*>(getFramework)))
        return false;

    void* framework{};
    __try {
        framework = getFramework(environment.game);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        framework = nullptr;
    }
    if (!framework || !ValidateObjectVtable(framework, {
            kGameFrameworkPauseGameSlot,
            kGameFrameworkGetSystemSlot }))
        return false;

    const auto getSystem = VFunc<GameFrameworkGetSystemFn>(
        framework, kGameFrameworkGetSystemSlot);
    void* frameworkSystem{};
    __try {
        frameworkSystem = getSystem ? getSystem(framework) : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        frameworkSystem = nullptr;
    }
    return frameworkSystem == environment.system;
}

bool StronglyValidateEnvironment(RuntimeEnvironment& candidate, RuntimeEnvironment& result)
{
    if (!candidate.base)
        return false;
    if (!ThreadBelongsToCurrentProcess(candidate.mainThreadId))
        return false;
    if (!ValidateGameAndFrameworkIdentity(candidate))
        return false;

    result = candidate;
    return true;
}

bool FindRuntimeEnvironment(
    HMODULE whGame,
    const kcd2::runtime::BuildProfile& profile,
    RuntimeEnvironment& result)
{
    result = {};
    RuntimeEnvironment candidate{};

    switch (profile.environmentLocator) {
    case kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan:
        // This strategy exists only to preserve the already-proven Xbox 1.5.6
        // discovery behavior. It is selected by a BuildProfile, not by storefront
        // branching, so another binary can never reach it unless explicitly registered.
        if (!LegacyFindRuntimeEnvironment_Xbox156Only(whGame, candidate))
            return false;
        break;

    case kcd2::runtime::EnvironmentLocatorStrategy::CanonicalPConsoleCodeAnchor: {
        std::uint8_t* canonicalEnvironment{};
        if (!kcd2::runtime::ResolveCanonicalEnvironmentBase(
                whGame, profile, canonicalEnvironment))
            return false;
        if (!ValidateEnvironmentCandidate(canonicalEnvironment, candidate))
            return false;
        break;
    }

    default:
        return false;
    }

    return StronglyValidateEnvironment(candidate, result);
}

DWORD WINAPI BootstrapThread(void*)
{
    Log("native bootstrap started; target=KCD2 Windows retail profiles; KCD2 Clean Pause v%s build=%s",
        CLEAN_PAUSE_VERSION, CLEAN_PAUSE_BUILD_ID);

    HMODULE whGame{};
    for (DWORD elapsed = 0; elapsed < kWaitForWhGameMs && !g_stopping.load(); elapsed += kPollMs) {
        whGame = GetModuleHandleW(L"WHGame.dll");
        if (whGame)
            break;
        Sleep(kPollMs);
    }

    if (!whGame) {
        Log("WHGame.dll not found; Clean Pause disabled");
        return 0;
    }

    kcd2::runtime::Fingerprint fingerprint{};
    if (!kcd2::runtime::ReadFingerprint(whGame, fingerprint)) {
        Log("WHGame fingerprint unavailable; Clean Pause disabled; no hooks installed");
        return 0;
    }

    Log(
        "WHGame fingerprint: TimeDateStamp=0x%08lx SizeOfImage=0x%08lx CheckSum=0x%08lx",
        static_cast<unsigned long>(fingerprint.timestamp),
        static_cast<unsigned long>(fingerprint.imageSize),
        static_cast<unsigned long>(fingerprint.checksum));

    const auto* profile = kcd2::runtime::MatchSupportedBuild(fingerprint);
    if (!profile) {
        Log("unsupported WHGame build; Clean Pause disabled; no hooks installed");
        return 0;
    }
    if (!profile->abi || !kcd2::runtime::MatureRuntimeSupports(*profile->abi)) {
        Log("matched build %s selects an ABI unsupported by this Clean Pause runtime; no hooks installed",
            profile->name);
        return 0;
    }

    Log(
        "WHGame profile accepted: %s; storefront=%s abi=%s locator=%s evidence=%s",
        profile->name,
        kcd2::runtime::StorefrontName(profile->storefront),
        profile->abi->name,
        kcd2::runtime::EnvironmentLocatorName(profile->environmentLocator),
        kcd2::runtime::BuildValidationName(profile->validation));

    RuntimeEnvironment environment{};
    for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs && !g_stopping.load(); elapsed += kPollMs) {
        if (FindRuntimeEnvironment(whGame, *profile, environment))
            break;
        Sleep(kPollMs);
    }

    if (!environment.base) {
        Log("supported %s runtime environment could not be strongly validated; no hooks installed",
            profile->name);
        return 0;
    }

    Log("runtime environment validated for %s; env=%p mainThread=%lu",
        profile->name,
        environment.base,
        static_cast<unsigned long>(environment.mainThreadId));
    if (!InstallInputHook(environment))
        Log("Clean Pause hook installation failed for %s; vanilla behavior retained where possible",
            profile->name);
    return 0;
}

} // namespace

bool Start(HMODULE selfModule)
{
    g_selfModule = selfModule;
    g_stopping.store(false, std::memory_order_relaxed);

    HANDLE thread = CreateThread(nullptr, 0, BootstrapThread, nullptr, 0, nullptr);
    if (!thread)
        return false;
    CloseHandle(thread);
    return true;
}

void Stop()
{
    g_stopping.store(true, std::memory_order_release);
}

} // namespace clean_pause
