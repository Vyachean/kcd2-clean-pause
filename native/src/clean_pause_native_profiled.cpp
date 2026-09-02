#include "kcd2_runtime_profile.h"

// Keep the mature Clean Pause implementation intact while replacing only its
// bootstrap/runtime-discovery boundary. The original scanner and IGame[16]
// framework lookup are retained solely for the already runtime-tested Xbox /
// Microsoft Store 1.5.6 path. Public Steam 1.5.6 RE identifies IGame[16] as a
// different engine-root object, while the real IGameFramework is the CCryAction
// singleton cached at qword_18549D328.
#define Start LegacyStart_Unreachable
#define Stop LegacyStop_Unreachable
#define BootstrapThread LegacyBootstrapThread_Unreachable
#define FindRuntimeEnvironment LegacyFindRuntimeEnvironment_Xbox156Only
#define ResolveGameFramework LegacyResolveGameFramework_Xbox156Only
#define InstallPauseBarrierHook LegacyInstallPauseBarrierHook_Xbox156Only
#define InstallInputHook LegacyInstallInputHook_Xbox156Only
#define HookPostInputEvent LegacyHookPostInputEventProfiledCore
#include "clean_pause_native.cpp"
#undef HookPostInputEvent
#undef InstallInputHook
#undef InstallPauseBarrierHook
#undef ResolveGameFramework
#undef FindRuntimeEnvironment
#undef BootstrapThread
#undef Stop
#undef Start

namespace clean_pause {
namespace {

constexpr DWORD kProfileSlowPollMs = 1'000;
constexpr ULONGLONG kProfileWaitHeartbeatMs = 30'000;
constexpr std::size_t kSteam156FrameworkStorageRva = 0x0549D328;
constexpr std::size_t kSteam156FrameworkVtableRva = 0x040472D0;

HMODULE g_profileWhGame{};
const kcd2::runtime::BuildProfile* g_activeBuildProfile{};

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

// The Xbox retail path already proved the legacy IGame[16] lookup in-game. Keep
// that accepted behavior isolated to Xbox rather than treating slot 16 as a
// storefront-independent IGameFramework accessor.
bool ValidateLegacyXboxGameAndFrameworkIdentity(const RuntimeEnvironment& environment)
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
    if (!ValidateLegacyXboxGameAndFrameworkIdentity(candidate))
        return false;

    result = candidate;
    return true;
}

// Exact-profile readiness deliberately validates only capabilities required for
// installing the mature input/menu runtime. PauseGame observation is optional in
// the mature runtime and must not disable Clean Pause when framework discovery is
// unavailable. This restores the original fail-open capability boundary.
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
            kGameGetNameSlot }))
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

    return nullptr;
}

bool ResolveSteamFrameworkSingleton(
    const RuntimeEnvironment& environment,
    void*& framework)
{
    framework = nullptr;
    if (!g_profileWhGame || !g_activeBuildProfile
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam
        || !environment.system)
        return false;

    auto* imageBase = reinterpret_cast<std::uint8_t*>(g_profileWhGame);
    auto* storage = imageBase + kSteam156FrameworkStorageRva;
    if (!IsReadable(storage, sizeof(void*)))
        return false;

    __try {
        framework = *reinterpret_cast<void**>(storage);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        framework = nullptr;
    }
    if (!framework || !IsReadable(framework, sizeof(void*)))
        return false;

    void** vtable{};
    __try {
        vtable = *reinterpret_cast<void***>(framework);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        vtable = nullptr;
    }
    if (vtable != reinterpret_cast<void**>(imageBase + kSteam156FrameworkVtableRva))
        return false;
    if (!ValidateObjectVtable(framework, {
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
    if (frameworkSystem != environment.system) {
        framework = nullptr;
        return false;
    }
    return true;
}

bool ResolveGameFramework(const RuntimeEnvironment& environment, void*& framework)
{
    framework = nullptr;
    if (g_activeBuildProfile) {
        if (g_activeBuildProfile->storefront == kcd2::runtime::Storefront::Steam)
            return ResolveSteamFrameworkSingleton(environment, framework);

        // GOG/Epic exact environments are valid for the input/menu fallback, but no
        // canonical framework singleton storage has yet been registered for them.
        // Do not reinterpret IGame[16] as IGameFramework on these binaries.
        if (g_activeBuildProfile->storefront != kcd2::runtime::Storefront::XboxMicrosoftStore)
            return false;
    }

    return LegacyResolveGameFramework_Xbox156Only(environment, framework);
}

void __fastcall HookPauseGameProfiled(
    void* framework,
    bool pause,
    bool force,
    unsigned int fadeOutInMs)
{
    const bool observe = framework == g_gameFramework
        && pause
        && g_pendingPauseAttempt.load(std::memory_order_acquire)
        && (!g_mainThreadId || GetCurrentThreadId() == g_mainThreadId);
    const ULONGLONG enteredAt = observe ? GetTickCount64() : 0;

    if (observe)
        g_pauseTransitionActive.store(true, std::memory_order_release);

    if (!g_originalPauseGame) {
        if (observe)
            g_pauseTransitionActive.store(false, std::memory_order_release);
        return;
    }
    g_originalPauseGame(framework, pause, force, fadeOutInMs);

    if (!observe || !g_pendingPauseAttempt.load(std::memory_order_acquire)) {
        if (observe)
            g_pauseTransitionActive.store(false, std::memory_order_release);
        return;
    }

    g_pauseBarrierObserved.store(true, std::memory_order_release);
    const ULONGLONG pressAt = g_pausePressAtMs.load(std::memory_order_acquire);
    Log(
        "vanilla IGameFramework::PauseGame(true) returned during pending pause; force=%s fadeMs=%u callMs=%llu pressToPauseMs=%llu",
        force ? "true" : "false",
        fadeOutInMs,
        static_cast<unsigned long long>(GetTickCount64() - enteredAt),
        static_cast<unsigned long long>(pressAt ? enteredAt - pressAt : 0));
}

bool InstallPauseBarrierHook(
    const RuntimeEnvironment& environment,
    bool logUnavailable)
{
    void* framework{};
    if (!ResolveGameFramework(environment, framework)) {
        if (logUnavailable)
            Log("IGameFramework pause barrier unavailable; continuing with Menu/input fallback");
        return false;
    }

    const auto target = reinterpret_cast<void*>(
        VFunc<PauseGameFn>(framework, kGameFrameworkPauseGameSlot));
    if (!target || !IsExecutable(target))
        return false;

    if (g_pauseGameTarget) {
        if (target != g_pauseGameTarget)
            return false;
        g_gameFramework = framework;
        return true;
    }

    const MH_STATUS create = MH_CreateHook(
        target,
        reinterpret_cast<void*>(&HookPauseGameProfiled),
        reinterpret_cast<void**>(&g_originalPauseGame));
    if (create != MH_OK) {
        Log("MH_CreateHook(IGameFramework::PauseGame) failed: %d", static_cast<int>(create));
        return false;
    }
    const MH_STATUS enable = MH_EnableHook(target);
    if (enable != MH_OK) {
        MH_RemoveHook(target);
        Log("MH_EnableHook(IGameFramework::PauseGame) failed: %d", static_cast<int>(enable));
        return false;
    }

    g_gameFramework = framework;
    g_pauseGameTarget = target;
    Log("vanilla IGameFramework::PauseGame observer active; framework=%p PauseGame=%p",
        g_gameFramework, g_pauseGameTarget);
    return true;
}

bool TryInstallDeferredSteamPauseBarrier()
{
    if (g_pauseGameTarget || !g_activeBuildProfile || !g_environment
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam)
        return g_pauseGameTarget != nullptr;

    RuntimeEnvironment environment{};
    environment.base = g_environment;
    __try {
        environment.system = *reinterpret_cast<void* const*>(
            reinterpret_cast<const std::uint8_t*>(g_environment) + kEnvSystemOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        environment.system = nullptr;
    }
    if (!environment.system)
        return false;

    const bool installed = InstallPauseBarrierHook(environment, false);
    if (installed)
        Log("deferred Steam IGameFramework pause barrier became ready on pause input");
    return installed;
}

bool ShouldTryDeferredSteamPauseBarrier(const InputEvent* event)
{
    if (!event || g_forwardDepth != 0 || g_pauseGameTarget
        || !g_activeBuildProfile
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam
        || (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId))
        return false;

    bool shouldTry{};
    __try {
        shouldTry = IsPauseKey(event->keyId)
            && (event->state & InputState::Pressed) != 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        shouldTry = false;
    }
    return shouldTry;
}

void __fastcall HookPostInputEventProfiled(void* input, const InputEvent* event, bool force)
{
    // The mature runtime already installs its Menu/HUD/Mask/Bubbles hooks from this
    // same first-Pause call stack, and pinned MinHook serializes its public API.
    // Acquire the optional Steam CCryAction barrier here as well: by real user input
    // the game lifecycle is mature, and avoiding a parallel bootstrap attempt removes
    // a create/enable race against the input thread. Failure stays fail-open and is
    // retried on the next physical Pause press.
    if (ShouldTryDeferredSteamPauseBarrier(event))
        TryInstallDeferredSteamPauseBarrier();

    LegacyHookPostInputEventProfiledCore(input, event, force);
}

bool InstallInputHook(const RuntimeEnvironment& environment)
{
    g_environment = environment.base;
    g_input = environment.input;
    g_game = environment.game;
    g_flashUI = environment.flashUI;
    g_mainThreadId = environment.mainThreadId;
    blur::Initialize(environment.scriptSystem, environment.mainThreadId);

    g_postInputEventTarget = reinterpret_cast<void*>(
        VFunc<PostInputEventFn>(g_input, kInputPostInputEventSlot));
    if (!g_postInputEventTarget || !IsExecutable(g_postInputEventTarget)) {
        Log("PostInputEvent vtable target is invalid; hook not installed");
        return false;
    }

    const MH_STATUS init = MH_Initialize();
    if (init != MH_OK && init != MH_ERROR_ALREADY_INITIALIZED) {
        Log("MH_Initialize failed: %d", static_cast<int>(init));
        return false;
    }

    // Install the required input/Menu path first. The PauseGame observer is a
    // strictly optional capability and must never leave a partial runtime behind
    // when the required PostInputEvent hook itself cannot be installed.
    const MH_STATUS create = MH_CreateHook(
        g_postInputEventTarget,
        reinterpret_cast<void*>(&HookPostInputEventProfiled),
        reinterpret_cast<void**>(&g_originalPostInputEvent));
    if (create != MH_OK) {
        Log("MH_CreateHook(PostInputEvent) failed: %d", static_cast<int>(create));
        return false;
    }

    const MH_STATUS enable = MH_EnableHook(g_postInputEventTarget);
    if (enable != MH_OK) {
        MH_RemoveHook(g_postInputEventTarget);
        g_originalPostInputEvent = nullptr;
        Log("MH_EnableHook(PostInputEvent) failed: %d", static_cast<int>(enable));
        return false;
    }

    Log(
        "KCD2 Clean Pause v%s build=%s active; env=%p input=%p game(IGame*)=%p flashUI=%p mainThread=%lu PostInputEvent=%p",
        CLEAN_PAUSE_VERSION,
        CLEAN_PAUSE_BUILD_ID,
        g_environment,
        g_input,
        g_game,
        g_flashUI,
        static_cast<unsigned long>(g_mainThreadId),
        g_postInputEventTarget);

    if (g_activeBuildProfile
        && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::Steam) {
        Log("Steam PauseGame observer will be acquired lazily on the first Pause input; Menu/input runtime is already active");
    } else if (g_activeBuildProfile
        && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::XboxMicrosoftStore) {
        // Preserve the already runtime-tested Xbox behavior. Unlike Steam, there is
        // no second installation path racing this bootstrap attempt.
        InstallPauseBarrierHook(environment, true);
    }
    return true;
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

    g_profileWhGame = whGame;
    g_activeBuildProfile = profile;

    Log(
        "WHGame profile candidate: %s; storefront=%s identity=%s abi=%s locator=%s evidence=%s",
        profile->name,
        kcd2::runtime::StorefrontName(profile->storefront),
        kcd2::runtime::BuildIdentityStrategyName(profile->identityStrategy),
        profile->abi->name,
        kcd2::runtime::EnvironmentLocatorName(profile->environmentLocator),
        kcd2::runtime::BuildValidationName(profile->validation));

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
        Log("matched %s runtime environment could not be validated; no hooks installed",
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