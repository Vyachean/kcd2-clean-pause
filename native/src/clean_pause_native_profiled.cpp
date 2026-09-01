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

constexpr DWORD kProfileSlowPollMs = 1'000;
constexpr ULONGLONG kProfileWaitHeartbeatMs = 30'000;

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

const char* ValidateProfileEnvironment(
    const std::uint8_t* environmentBase,
    RuntimeEnvironment& candidate)
{
    candidate = {};
    if (!environmentBase || !IsReadable(environmentBase, kEnvSize))
        return "environment-memory-unreadable";

    __try {
        candidate.base = const_cast<std::uint8_t*>(environmentBase);
        candidate.scriptSystem = *reinterpret_cast<void* const*>(
            environmentBase + kEnvScriptSystemOffset);
        candidate.input = *reinterpret_cast<void* const*>(
            environmentBase + kEnvInputOffset);
        candidate.game = *reinterpret_cast<void* const*>(
            environmentBase + kEnvGameOffset);
        candidate.system = *reinterpret_cast<void* const*>(
            environmentBase + kEnvSystemOffset);
        candidate.flashUI = *reinterpret_cast<void* const*>(
            environmentBase + kEnvFlashUIOffset);
        candidate.mainThreadId = *reinterpret_cast<const DWORD*>(
            environmentBase + kEnvMainThreadIdOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        candidate = {};
        return "environment-field-read-failed";
    }

    if (!candidate.scriptSystem || !candidate.input || !candidate.game
        || !candidate.system || !candidate.flashUI || candidate.mainThreadId == 0)
        return "required-interface-not-ready";
    if (candidate.scriptSystem == candidate.input || candidate.input == candidate.game
        || candidate.game == candidate.system || candidate.system == candidate.flashUI)
        return "environment-interface-alias";

    if (!ValidateObjectVtable(candidate.scriptSystem, {
            kScriptExecuteBufferSlot,
            kScriptGetGlobalAnySlot }))
        return "script-system-vtable";
    if (!ValidateObjectVtable(candidate.input, {kInputPostInputEventSlot}))
        return "input-vtable";
    if (!ValidateObjectVtable(candidate.game, {
            kGameGetLongNameSlot,
            kGameGetNameSlot,
            kGameGetFrameworkSlot }))
        return "game-vtable";
    if (!ValidateObjectVtable(candidate.system, {0}))
        return "system-vtable";
    if (!ValidateObjectVtable(candidate.flashUI, {kFlashUIGetElementByInstanceStrSlot}))
        return "flash-ui-vtable";

    HANDLE thread = OpenThread(
        THREAD_QUERY_LIMITED_INFORMATION, FALSE, candidate.mainThreadId);
    if (!thread)
        return "main-thread-unavailable";
    const DWORD ownerProcess = GetProcessIdOfThread(thread);
    CloseHandle(thread);
    if (ownerProcess == 0 || ownerProcess != GetCurrentProcessId())
        return "main-thread-owner-mismatch";

    using GetGameNameFn = const char*(__fastcall*)(void*);
    const auto getName = VFunc<GetGameNameFn>(candidate.game, kGameGetNameSlot);
    const char* gameName{};
    bool nameMatches{};
    __try {
        gameName = getName ? getName(candidate.game) : nullptr;
        nameMatches = gameName && std::strcmp(gameName, "kcd2") == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        nameMatches = false;
    }
    if (!nameMatches)
        return "game-name-mismatch";

    const auto getFramework = VFunc<GetGameFrameworkFn>(
        candidate.game, kGameGetFrameworkSlot);
    if (!getFramework || !IsExecutable(reinterpret_cast<void*>(getFramework)))
        return "game-framework-accessor";

    void* framework{};
    __try {
        framework = getFramework(candidate.game);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        framework = nullptr;
    }
    if (!framework)
        return "game-framework-not-ready";
    if (!ValidateObjectVtable(framework, {
            kGameFrameworkPauseGameSlot,
            kGameFrameworkGetSystemSlot }))
        return "game-framework-vtable";

    const auto getSystem = VFunc<GameFrameworkGetSystemFn>(
        framework, kGameFrameworkGetSystemSlot);
    void* frameworkSystem{};
    __try {
        frameworkSystem = getSystem ? getSystem(framework) : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        frameworkSystem = nullptr;
    }
    if (frameworkSystem != candidate.system)
        return "framework-system-mismatch";

    return nullptr;
}

bool PollRuntimeEnvironment(
    HMODULE whGame,
    const kcd2::runtime::BuildProfile& profile,
    const std::uint8_t* fixedEnvironmentBase,
    RuntimeEnvironment& result,
    RuntimeEnvironment& observedCandidate,
    const char*& failureReason)
{
    result = {};
    observedCandidate = {};
    failureReason = nullptr;
    RuntimeEnvironment candidate{};

    switch (profile.environmentLocator) {
    case kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan:
        if (!LegacyFindRuntimeEnvironment_Xbox156Only(whGame, candidate)) {
            failureReason = "xbox-runtime-not-ready";
            return false;
        }
        observedCandidate = candidate;
        if (!StronglyValidateEnvironment(candidate, result)) {
            failureReason = "xbox-runtime-identity";
            return false;
        }
        return true;

    case kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRva:
    case kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation:
        failureReason = ValidateProfileEnvironment(fixedEnvironmentBase, candidate);
        observedCandidate = candidate;
        if (failureReason)
            return false;
        result = candidate;
        return true;

    default:
        failureReason = "unsupported-locator";
        return false;
    }
}

void LogProfileWaitState(
    const kcd2::runtime::BuildProfile& profile,
    const char* reason,
    const RuntimeEnvironment& candidate,
    const char* prefix)
{
    Log(
        "%s %s runtime readiness: reason=%s env=%p script=%p input=%p game=%p system=%p flashUI=%p mainThread=%lu",
        prefix,
        profile.name,
        reason ? reason : "unknown",
        candidate.base,
        candidate.scriptSystem,
        candidate.input,
        candidate.game,
        candidate.system,
        candidate.flashUI,
        static_cast<unsigned long>(candidate.mainThreadId));
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

    kcd2::runtime::DetectedBuildIdentity identity{};
    if (!kcd2::runtime::ReadBuildIdentity(whGame, identity)) {
        Log("WHGame build identity unavailable; Clean Pause disabled; no hooks installed");
        return 0;
    }

    Log(
        "WHGame fingerprint: TimeDateStamp=0x%08lx SizeOfImage=0x%08lx CheckSum=0x%08lx",
        static_cast<unsigned long>(identity.fingerprint.timestamp),
        static_cast<unsigned long>(identity.fingerprint.imageSize),
        static_cast<unsigned long>(identity.fingerprint.checksum));
    Log(
        "WHGame metadata: storefront=%s build=%s",
        kcd2::runtime::StorefrontName(identity.storefront),
        identity.buildCode.empty() ? "<unavailable>" : identity.buildCode.c_str());

    const auto* profile = kcd2::runtime::MatchSupportedBuild(identity);
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
        "WHGame profile candidate: %s; storefront=%s identity=%s abi=%s locator=%s evidence=%s",
        profile->name,
        kcd2::runtime::StorefrontName(profile->storefront),
        kcd2::runtime::BuildIdentityStrategyName(profile->identityStrategy),
        profile->abi->name,
        kcd2::runtime::EnvironmentLocatorName(profile->environmentLocator),
        kcd2::runtime::BuildValidationName(profile->validation));

    // Resolve immutable build-level identity exactly once. For profiled retail
    // builds this avoids rescanning WHGame.dll on every readiness poll. The poll
    // below only waits for interfaces inside that already identified gEnv to become
    // live. Xbox retains the bounded legacy path that was already runtime-tested.
    std::uint8_t* fixedEnvironmentBase{};
    const bool hasExactEnvironment =
        profile->environmentLocator
            == kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRva
        || profile->environmentLocator
            == kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation;
    if (hasExactEnvironment) {
        if (!kcd2::runtime::ResolveProfileEnvironmentBase(
                whGame, *profile, fixedEnvironmentBase)) {
            Log("matched %s build-level environment identity failed validation; no hooks installed",
                profile->name);
            return 0;
        }
        Log("build-level environment identity validated for %s; env=%p",
            profile->name, fixedEnvironmentBase);
    }

    RuntimeEnvironment environment{};
    if (hasExactEnvironment) {
        const ULONGLONG waitStartedAt = GetTickCount64();
        ULONGLONG lastWaitLogAt{};
        std::string lastReason;

        while (!g_stopping.load()) {
            RuntimeEnvironment candidate{};
            const char* failureReason{};
            if (PollRuntimeEnvironment(
                    whGame,
                    *profile,
                    fixedEnvironmentBase,
                    environment,
                    candidate,
                    failureReason))
                break;

            const ULONGLONG now = GetTickCount64();
            const std::string reason = failureReason ? failureReason : "unknown";
            if (reason != lastReason) {
                LogProfileWaitState(*profile, failureReason, candidate, "waiting for");
                lastReason = reason;
                lastWaitLogAt = now;
            } else if (now - lastWaitLogAt >= kProfileWaitHeartbeatMs) {
                LogProfileWaitState(*profile, failureReason, candidate, "still waiting for");
                lastWaitLogAt = now;
            }

            const DWORD delay = now - waitStartedAt < kWaitForRuntimeMs
                ? kPollMs
                : kProfileSlowPollMs;
            Sleep(delay);
        }
    } else {
        for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs && !g_stopping.load(); elapsed += kPollMs) {
            RuntimeEnvironment candidate{};
            const char* failureReason{};
            if (PollRuntimeEnvironment(
                    whGame,
                    *profile,
                    fixedEnvironmentBase,
                    environment,
                    candidate,
                    failureReason))
                break;
            Sleep(kPollMs);
        }
    }

    if (g_stopping.load())
        return 0;
    if (!environment.base) {
        Log("matched %s runtime environment could not be strongly validated; no hooks installed",
            profile->name);
        return 0;
    }

    Log("runtime profile validated for %s; env=%p mainThread=%lu",
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
