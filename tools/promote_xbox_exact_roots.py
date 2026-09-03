#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- profile header ---------------------------------------------------------
path = ROOT / "native/src/kcd2_runtime_profile.h"
text = path.read_text(encoding="utf-8")
text = text.replace('''enum class EnvironmentLocatorStrategy {
    ExactEnvironmentRva,
    ExactEnvironmentRvaWithAnchorValidation,
    LegacyXbox156ValidatedScan,
};

enum class FrameworkLocatorStrategy {
    None,
    ExactSingletonRva,
    LegacyGameFrameworkSlot,
};
''', '''enum class EnvironmentLocatorStrategy {
    ExactEnvironmentRva,
    ExactEnvironmentRvaWithAnchorValidation,
};

enum class FrameworkLocatorStrategy {
    None,
    ExactPointerStorageRva,
    ExactObjectRva,
};
''')
text = text.replace('''    FrameworkLocatorStrategy frameworkLocator{};
    std::uint32_t expectedFrameworkStorageRva{};
    std::uint32_t expectedFrameworkVtableRva{};
''', '''    FrameworkLocatorStrategy frameworkLocator{};
    std::uint32_t expectedFrameworkRva{};
    std::uint32_t expectedFrameworkVtableRva{};
''')
path.write_text(text, encoding="utf-8")

# --- profile data -----------------------------------------------------------
path = ROOT / "native/src/kcd2_runtime_profile.cpp"
text = path.read_text(encoding="utf-8")
old_xbox = '''        0,
        0,
        EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan,
        FrameworkLocatorStrategy::LegacyGameFrameworkSlot,
        0,
        0,
        {false, false, false},
'''
new_xbox = '''        0,
        0x049d6ef8,
        EnvironmentLocatorStrategy::ExactEnvironmentRva,
        FrameworkLocatorStrategy::ExactObjectRva,
        0x056ec680,
        0x040daf18,
        {false, false, false},
'''
if old_xbox not in text:
    raise RuntimeError("Xbox profile block not found")
text = text.replace(old_xbox, new_xbox, 1)
text = text.replace("FrameworkLocatorStrategy::ExactSingletonRva", "FrameworkLocatorStrategy::ExactPointerStorageRva")
text = text.replace('''    case EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan:
        return "legacy-xbox-1.5.6-validated-scan";
''', '')
text = text.replace('''    case FrameworkLocatorStrategy::ExactPointerStorageRva:
        return "exact-singleton-rva";
    case FrameworkLocatorStrategy::LegacyGameFrameworkSlot:
        return "legacy-game-framework-slot";
''', '''    case FrameworkLocatorStrategy::ExactPointerStorageRva:
        return "exact-pointer-storage-rva";
    case FrameworkLocatorStrategy::ExactObjectRva:
        return "exact-object-rva";
''')
path.write_text(text, encoding="utf-8")

# --- shared runtime ---------------------------------------------------------
path = ROOT / "native/src/clean_pause_native.cpp"
text = path.read_text(encoding="utf-8")

# Remove the writable-memory environment scanner entirely.
start = text.index("bool LegacyFindRuntimeEnvironment_Xbox156Only")
end = text.index("bool ResolveMenuElement", start)
text = text[:start] + text[end:]

# Remove the IGame[16] framework adapter entirely.
start = text.index("bool LegacyResolveGameFramework_Xbox156Only")
end = text.index("} // namespace\n\n} // namespace clean_pause", start)
text = text[:start] + text[end:]

start = text.index("bool ResolveProfileFrameworkSingleton")
end = text.index("bool ShouldSuppressProfileHudRootVisibility", start)
new_framework = r'''bool ResolveProfileFramework(
    const RuntimeEnvironment& environment,
    void*& framework)
{
    framework = nullptr;
    if (!g_profileWhGame || !g_activeBuildProfile
        || g_activeBuildProfile->frameworkLocator
            == kcd2::runtime::FrameworkLocatorStrategy::None
        || !g_activeBuildProfile->expectedFrameworkRva
        || !g_activeBuildProfile->expectedFrameworkVtableRva
        || !environment.system)
        return false;

    auto* imageBase = reinterpret_cast<std::uint8_t*>(g_profileWhGame);
    switch (g_activeBuildProfile->frameworkLocator) {
    case kcd2::runtime::FrameworkLocatorStrategy::ExactPointerStorageRva: {
        auto* storage = imageBase + g_activeBuildProfile->expectedFrameworkRva;
        if (!IsReadable(storage, sizeof(void*)))
            return false;
        __try {
            framework = *reinterpret_cast<void**>(storage);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            framework = nullptr;
        }
        break;
    }
    case kcd2::runtime::FrameworkLocatorStrategy::ExactObjectRva:
        framework = imageBase + g_activeBuildProfile->expectedFrameworkRva;
        break;
    case kcd2::runtime::FrameworkLocatorStrategy::None:
    default:
        return false;
    }

    if (!framework || !IsReadable(framework, sizeof(void*)))
        return false;

    void** vtable{};
    __try {
        vtable = *reinterpret_cast<void***>(framework);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        vtable = nullptr;
    }
    if (vtable != reinterpret_cast<void**>(
            imageBase + g_activeBuildProfile->expectedFrameworkVtableRva)) {
        framework = nullptr;
        return false;
    }
    if (!ValidateObjectVtable(framework, {
            kGameFrameworkPauseGameSlot,
            kGameFrameworkGetSystemSlot })) {
        framework = nullptr;
        return false;
    }

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
    return ResolveProfileFramework(environment, framework);
}

'''
text = text[:start] + new_framework + text[end:]

# All supported profiles now have immutable build-level environment RVAs.
start = text.index("bool PollRuntimeEnvironment(")
end = text.index("void LogProfileWaitState", start)
new_poll = r'''bool PollRuntimeEnvironment(
    HMODULE,
    const kcd2::runtime::BuildProfile&,
    const std::uint8_t* fixedEnvironmentBase,
    RuntimeEnvironment& result,
    RuntimeEnvironment& observedCandidate,
    const char*& failureReason)
{
    result = {};
    observedCandidate = {};
    failureReason = nullptr;

    if (!fixedEnvironmentBase) {
        failureReason = "environment-base-unavailable";
        return false;
    }

    RuntimeEnvironment candidate{};
    failureReason = ValidateProfileEnvironment(fixedEnvironmentBase, candidate);
    observedCandidate = candidate;
    if (failureReason)
        return false;
    result = candidate;
    return true;
}

'''
text = text[:start] + new_poll + text[end:]

# Simplify bootstrap: there is no legacy discovery class left.
old_bootstrap = '''    std::uint8_t* fixedEnvironmentBase{};
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
'''
new_bootstrap = '''    std::uint8_t* fixedEnvironmentBase{};
    if (!kcd2::runtime::ResolveProfileEnvironmentBase(
            whGame, *profile, fixedEnvironmentBase)) {
        Log("matched %s build-level environment identity failed validation; no hooks installed",
            profile->name);
        return 0;
    }
    Log("build-level environment identity validated for %s; env=%p",
        profile->name, fixedEnvironmentBase);

    RuntimeEnvironment environment{};
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
'''
if old_bootstrap not in text:
    raise RuntimeError("bootstrap environment split not found")
text = text.replace(old_bootstrap, new_bootstrap, 1)
path.write_text(text, encoding="utf-8")

# --- executable profile tests ----------------------------------------------
path = ROOT / "native/tests/runtime_profile_tests.cpp"
text = path.read_text(encoding="utf-8")
text = text.replace("FrameworkLocatorStrategy::ExactSingletonRva", "FrameworkLocatorStrategy::ExactPointerStorageRva")
text = text.replace("expectedFrameworkStorageRva", "expectedFrameworkRva")
old = '''    CHECK(xboxProfile->environmentLocator
        == kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan);
    CHECK(xboxProfile->frameworkLocator
        == kcd2::runtime::FrameworkLocatorStrategy::LegacyGameFrameworkSlot);
'''
new = '''    CHECK(xboxProfile->environmentLocator
        == kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRva);
    CHECK(xboxProfile->expectedEnvironmentRva == 0x049d6ef8);
    CHECK(xboxProfile->frameworkLocator
        == kcd2::runtime::FrameworkLocatorStrategy::ExactObjectRva);
    CHECK(xboxProfile->expectedFrameworkRva == 0x056ec680);
    CHECK(xboxProfile->expectedFrameworkVtableRva == 0x040daf18);
'''
if old not in text:
    raise RuntimeError("Xbox runtime profile test block not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

# --- Python contracts -------------------------------------------------------
path = ROOT / "tests/test_pause_barrier_contract.py"
text = path.read_text(encoding="utf-8")
start = text.index("    def test_framework_identity_is_not_shape_only")
end = text.index("    def test_pause_hook_keeps_exact_vanilla_ownership", start)
replacement = '''    def test_framework_identity_is_not_shape_only(self):
        resolver = NATIVE[
            NATIVE.index("bool ResolveProfileFramework"):
            NATIVE.index("bool ShouldSuppressProfileHudRootVisibility")
        ]
        self.assertIn("FrameworkLocatorStrategy::ExactPointerStorageRva", resolver)
        self.assertIn("FrameworkLocatorStrategy::ExactObjectRva", resolver)
        self.assertIn("expectedFrameworkRva", resolver)
        self.assertIn("expectedFrameworkVtableRva", resolver)
        self.assertIn("frameworkSystem != environment.system", resolver)
        self.assertIn("kGameFrameworkGetSystemSlot", resolver)
        self.assertNotIn("kGameGetFrameworkSlot", resolver)
        self.assertNotIn("LegacyResolveGameFramework_Xbox156Only", resolver)

'''
text = text[:start] + replacement + text[end:]
path.write_text(text, encoding="utf-8")

path = ROOT / "tests/test_runtime_profile_contract.py"
text = path.read_text(encoding="utf-8")
text = text.replace("expectedFrameworkStorageRva", "expectedFrameworkRva")
text = text.replace("FrameworkLocatorStrategy::ExactSingletonRva", "FrameworkLocatorStrategy::ExactPointerStorageRva")
text = text.replace('''    def test_profiled_non_xbox_environment_resolution_is_one_time_and_evidence_specific(self):
''', '''    def test_profiled_environment_resolution_is_one_time_and_evidence_specific(self):
''')
# Replace old strategy/legacy-specific tests with exact-root assertions.
start = text.index("    def test_framework_singleton_is_profile_data_not_storefront_logic")
end = text.index("    def test_required_input_hook_is_installed_before_optional_pause_barrier", start)
replacement = '''    def test_framework_roots_are_profile_data_not_storefront_logic(self):
        resolver = RUNTIME[
            RUNTIME.index("bool ResolveProfileFramework"):
            RUNTIME.index("bool ShouldSuppressProfileHudRootVisibility")
        ]
        self.assertIn("FrameworkLocatorStrategy::ExactPointerStorageRva", PROFILE)
        self.assertIn("FrameworkLocatorStrategy::ExactObjectRva", PROFILE)
        self.assertIn("0x0549d328", PROFILE.lower())
        self.assertIn("0x056ec680", PROFILE.lower())
        self.assertIn("0x040472d0", PROFILE.lower())
        self.assertIn("0x040daf18", PROFILE.lower())
        self.assertIn("expectedFrameworkRva", resolver)
        self.assertIn("expectedFrameworkVtableRva", resolver)
        self.assertIn("kGameFrameworkPauseGameSlot", resolver)
        self.assertIn("kGameFrameworkGetSystemSlot", resolver)
        self.assertIn("frameworkSystem != environment.system", resolver)
        self.assertNotIn("Storefront::Steam", resolver)
        self.assertNotIn("Storefront::XboxMicrosoftStore", resolver)
        self.assertNotIn("kGameGetFrameworkSlot", resolver)

'''
text = text[:start] + replacement + text[end:]
start = text.index("    def test_framework_dispatch_is_strategy_driven")
end = text.index("    def test_unknown_build_is_rejected_before_abi_or_runtime_discovery", start)
replacement = '''    def test_framework_dispatch_is_strategy_driven(self):
        resolver = RUNTIME[
            RUNTIME.index("bool ResolveProfileFramework"):
            RUNTIME.index("bool ShouldSuppressProfileHudRootVisibility")
        ]
        self.assertIn("FrameworkLocatorStrategy::ExactPointerStorageRva", resolver)
        self.assertIn("FrameworkLocatorStrategy::ExactObjectRva", resolver)
        self.assertIn("FrameworkLocatorStrategy::None", resolver)
        self.assertNotIn("LegacyResolveGameFramework_Xbox156Only", RUNTIME)
        self.assertNotIn("Storefront::Steam", resolver)
        self.assertNotIn("Storefront::XboxMicrosoftStore", resolver)
        self.assertNotIn("kGameGetFrameworkSlot", resolver)

    def test_xbox_uses_exact_runtime_roots(self):
        profile = PROFILE.lower()
        self.assertIn("0x049d6ef8", profile)
        self.assertIn("0x056ec680", profile)
        self.assertIn("0x040daf18", profile)
        self.assertNotIn("legacyxbox156validatedscan", PROFILE)
        self.assertNotIn("legacygameframeworkslot", PROFILE)
        self.assertNotIn("LegacyFindRuntimeEnvironment_Xbox156Only", RUNTIME)
        self.assertNotIn("LegacyResolveGameFramework_Xbox156Only", RUNTIME)
        self.assertNotIn("for (std::size_t offset = 0; offset <= limit", RUNTIME)

'''
text = text[:start] + replacement + text[end:]
# Bootstrap no longer has a legacy timeout branch.
text = text.replace('''        exact_start = bootstrap.index("if (hasExactEnvironment)", bootstrap.index("RuntimeEnvironment environment"))
        legacy_loop = bootstrap.index(
            "for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs",
            exact_start,
        )
        exact_wait = bootstrap[exact_start:legacy_loop]
        self.assertIn("while (!g_stopping.load())", exact_wait)
        self.assertIn("kProfileSlowPollMs", exact_wait)
        self.assertIn("kProfileWaitHeartbeatMs", RUNTIME)
        self.assertNotIn("could not be validated", exact_wait)
        self.assertIn(
            "for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs",
            bootstrap[legacy_loop:],
        )
''', '''        wait = bootstrap[bootstrap.index("RuntimeEnvironment environment"):]
        self.assertIn("while (!g_stopping.load())", wait)
        self.assertIn("kProfileSlowPollMs", wait)
        self.assertIn("kProfileWaitHeartbeatMs", RUNTIME)
        self.assertNotIn("for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs", wait)
''')
path.write_text(text, encoding="utf-8")

# --- stable checker ---------------------------------------------------------
path = ROOT / "tools/validate_native_contract.py"
text = path.read_text(encoding="utf-8")
# Remove legacy Xbox resolver checker block if present.
marker = 'xbox_resolver = native['
if marker in text:
    start = text.index(marker)
    end = text.index('profile_singleton_resolver = native[', start)
    text = text[:start] + text[end:]
text = text.replace("profile_singleton_resolver", "profile_framework_resolver")
text = text.replace("ResolveProfileFrameworkSingleton", "ResolveProfileFramework")
text = text.replace("FrameworkLocatorStrategy::ExactSingletonRva", "FrameworkLocatorStrategy::ExactPointerStorageRva")
text = text.replace("expectedFrameworkStorageRva", "expectedFrameworkRva")
text = text.replace('''    "FrameworkLocatorStrategy::LegacyGameFrameworkSlot",
''', '''    "FrameworkLocatorStrategy::ExactObjectRva",
''')
text = text.replace('''    "LegacyResolveGameFramework_Xbox156Only",
''', '')
text = text.replace('''if "kGameGetFrameworkSlot" in profile_framework_resolver:
    raise SystemExit("profile singleton framework resolver must not fall back to legacy IGame[16]")
''', '''if "kGameGetFrameworkSlot" in profile_framework_resolver:
    raise SystemExit("profile framework resolver must not use legacy IGame[16]")
''')
path.write_text(text, encoding="utf-8")

# --- docs ------------------------------------------------------------------
path = ROOT / "docs/DESIGN.md"
text = path.read_text(encoding="utf-8")
text = text.replace('''### Xbox / Microsoft Store 1.5.6

The runtime-tested Xbox path keeps its captured legacy environment scan and the separately proven `IGame[16] -> IGameFramework` lookup. That slot-16 interpretation is scoped to this Xbox adapter and is not a universal release_1_5 assumption.
''', '''### Xbox / Microsoft Store 1.5.6

Runtime capture on the exact Xbox PE fingerprint established canonical ASLR-independent roots: `gEnv` at RVA `0x049D6EF8` and the static `IGameFramework` object at RVA `0x056EC680`, with vtable RVA `0x040DAF18`. Xbox therefore uses the same exact-profile model as the other builds and no longer scans writable memory or calls the historical `IGame[16]` adapter at runtime.
''')
path.write_text(text, encoding="utf-8")

print("promoted Xbox runtime roots to exact profile data")
