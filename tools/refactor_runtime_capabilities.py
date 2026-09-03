#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PROFILE_CPP = ROOT / "native/src/kcd2_runtime_profile.cpp"
RUNTIME = ROOT / "native/src/clean_pause_native.cpp"
TEST_PROFILE = ROOT / "tests/test_runtime_profile_contract.py"
TEST_VISIBLE = ROOT / "tests/test_visible_pause_gesture_contract.py"
TEST_STEAM_NAME = ROOT / "tests/test_steam_game_name_identity.py"
TEST_PAUSE = ROOT / "tests/test_pause_barrier_contract.py"
VALIDATE = ROOT / "tools/validate_native_contract.py"
NATIVE_TEST = ROOT / "native/tests/runtime_profile_tests.cpp"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"{label}: expected text not found")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Build-profile data owns framework discovery and presentation capabilities.
# ---------------------------------------------------------------------------
profile = PROFILE_CPP.read_text(encoding="utf-8")
start = profile.index("const std::array<BuildProfile, 4> kSupportedBuilds{{")
end = profile.index("\nbool IsReadable", start)
profile_table = r'''const std::array<BuildProfile, 4> kSupportedBuilds{{
    {
        Storefront::XboxMicrosoftStore,
        "Xbox / Microsoft Store 1.5.6",
        BuildIdentityStrategy::ExactPeFingerprint,
        {0x6a391f7b, 0x05bf2000, 0x00000000},
        nullptr,
        0,
        0,
        EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan,
        FrameworkLocatorStrategy::LegacyGameFrameworkSlot,
        0,
        0,
        {false, false, false},
        &Release15AbiProfile(),
        BuildValidationLevel::RuntimeTested,
    },
    {
        Storefront::Steam,
        "Steam 1.5.6 release_1_5-15693",
        BuildIdentityStrategy::ExactPeFingerprint,
        {0x6a350e20, 0x05b2d000, 0x00000000},
        "release_1_5-15693",
        0,
        0x0492d7f8,
        EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation,
        FrameworkLocatorStrategy::ExactSingletonRva,
        0x0549d328,
        0x040472d0,
        {true, true, true},
        &Release15AbiProfile(),
        BuildValidationLevel::StaticReverseEngineering,
    },
    {
        Storefront::GOG,
        "GOG 1.5.6 release_1_5-15693",
        BuildIdentityStrategy::StorefrontBuildCode,
        {},
        "release_1_5-15693",
        0,
        0x049177f8,
        EnvironmentLocatorStrategy::ExactEnvironmentRva,
        FrameworkLocatorStrategy::None,
        0,
        0,
        {false, false, false},
        &Release15AbiProfile(),
        BuildValidationLevel::ExternalRuntimeEvidence,
    },
    {
        Storefront::EpicGamesStore,
        "Epic Games Store 1.5.6 release_1_5-15693",
        BuildIdentityStrategy::StorefrontBuildCode,
        {},
        "release_1_5-15693",
        0x6a34f917,
        0x0491d8b8,
        EnvironmentLocatorStrategy::ExactEnvironmentRva,
        FrameworkLocatorStrategy::None,
        0,
        0,
        {false, false, false},
        &Release15AbiProfile(),
        BuildValidationLevel::ExternalRuntimeEvidence,
    },
}};
'''
profile = profile[:start] + profile_table + profile[end:]

old_names = '''const char* BuildValidationName(BuildValidationLevel validation)
{'''
new_names = '''const char* FrameworkLocatorName(FrameworkLocatorStrategy strategy)
{
    switch (strategy) {
    case FrameworkLocatorStrategy::None:
        return "none";
    case FrameworkLocatorStrategy::ExactSingletonRva:
        return "exact-singleton-rva";
    case FrameworkLocatorStrategy::LegacyGameFrameworkSlot:
        return "legacy-game-framework-slot";
    default:
        return "unknown-framework-locator";
    }
}

const char* BuildValidationName(BuildValidationLevel validation)
{'''
profile = replace_once(profile, old_names, new_names, "framework locator name")
PROFILE_CPP.write_text(profile, encoding="utf-8")


# ---------------------------------------------------------------------------
# Shared Clean Pause behavior consumes profile capabilities, not storefront IDs.
# ---------------------------------------------------------------------------
runtime = RUNTIME.read_text(encoding="utf-8")

for old, new in (
    ("g_steamEntryRenderPrehide", "g_entryRenderPrehide"),
    ("ResolveSteamFrameworkSingleton", "ResolveProfileFrameworkSingleton"),
    ("ShouldSuppressSteamHudRootVisibility", "ShouldSuppressProfileHudRootVisibility"),
    ("ShouldPrehideSteamEntryRender", "ShouldPrehideEntryRender"),
    ("RollBackSteamEntryRenderPrehide", "RollBackEntryRenderPrehide"),
    ("TryInstallDeferredSteamPauseBarrier", "TryInstallDeferredPauseBarrier"),
    ("ShouldTryDeferredSteamPauseBarrier", "ShouldTryDeferredPauseBarrier"),
):
    runtime = runtime.replace(old, new)

runtime = runtime.replace("constexpr std::size_t kSteam156FrameworkStorageRva = 0x0549D328;\n", "")
runtime = runtime.replace("constexpr std::size_t kSteam156FrameworkVtableRva = 0x040472D0;\n", "")

marker = "std::atomic_bool g_entryRenderPrehide{false};\n"
helper = '''std::atomic_bool g_entryRenderPrehide{false};

const kcd2::runtime::RuntimeCapabilities& ActiveRuntimeCapabilities()
{
    static constexpr kcd2::runtime::RuntimeCapabilities kNone{};
    return g_activeBuildProfile ? g_activeBuildProfile->capabilities : kNone;
}
'''
runtime = replace_once(runtime, marker, helper, "active capabilities helper")

old_singleton_prefix = '''bool ResolveProfileFrameworkSingleton(
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
'''
new_singleton_prefix = '''bool ResolveProfileFrameworkSingleton(
    const RuntimeEnvironment& environment,
    void*& framework)
{
    framework = nullptr;
    if (!g_profileWhGame || !g_activeBuildProfile
        || g_activeBuildProfile->frameworkLocator
            != kcd2::runtime::FrameworkLocatorStrategy::ExactSingletonRva
        || !g_activeBuildProfile->expectedFrameworkStorageRva
        || !g_activeBuildProfile->expectedFrameworkVtableRva
        || !environment.system)
        return false;

    auto* imageBase = reinterpret_cast<std::uint8_t*>(g_profileWhGame);
    auto* storage = imageBase + g_activeBuildProfile->expectedFrameworkStorageRva;
'''
runtime = replace_once(runtime, old_singleton_prefix, new_singleton_prefix, "singleton resolver prefix")
runtime = runtime.replace(
    "if (vtable != reinterpret_cast<void**>(imageBase + kSteam156FrameworkVtableRva))",
    "if (vtable != reinterpret_cast<void**>(\n            imageBase + g_activeBuildProfile->expectedFrameworkVtableRva))",
    1,
)

resolver_start = runtime.index("bool ResolveGameFramework(const RuntimeEnvironment& environment, void*& framework)")
resolver_end = runtime.index("\nbool ShouldSuppressProfileHudRootVisibility", resolver_start)
new_resolver = '''bool ResolveGameFramework(const RuntimeEnvironment& environment, void*& framework)
{
    framework = nullptr;
    if (!g_activeBuildProfile)
        return false;

    switch (g_activeBuildProfile->frameworkLocator) {
    case kcd2::runtime::FrameworkLocatorStrategy::ExactSingletonRva:
        return ResolveProfileFrameworkSingleton(environment, framework);
    case kcd2::runtime::FrameworkLocatorStrategy::LegacyGameFrameworkSlot:
        return LegacyResolveGameFramework_Xbox156Only(environment, framework);
    case kcd2::runtime::FrameworkLocatorStrategy::None:
    default:
        return false;
    }
}
'''
runtime = runtime[:resolver_start] + new_resolver + runtime[resolver_end:]

old_root = '''bool ShouldSuppressProfileHudRootVisibility(bool visible)
{
    if (!g_activeBuildProfile
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam
        || g_hudMaskPinSuspended.load(std::memory_order_acquire)
        || !g_gameplayHudSnapshot.captured)
        return false;
'''
new_root = '''bool ShouldSuppressProfileHudRootVisibility(bool visible)
{
    if (!ActiveRuntimeCapabilities().pinHudRootDuringPause
        || g_hudMaskPinSuspended.load(std::memory_order_acquire)
        || !g_gameplayHudSnapshot.captured)
        return false;
'''
runtime = replace_once(runtime, old_root, new_root, "root visibility capability")
runtime = runtime.replace(
    'Log("Steam pause transition suppressed hud@0 root visibility change; preserved gameplay root=%s",',
    'Log("profile pause transition suppressed hud@0 root visibility change; preserved gameplay root=%s",',
    1,
)

old_prehide = '''bool ShouldPrehideEntryRender()
{
    return g_activeBuildProfile
        && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::Steam
        && g_menuElement
        && g_renderTarget
        && g_gameplayHudSnapshot.captured;
}
'''
new_prehide = '''bool ShouldPrehideEntryRender()
{
    return ActiveRuntimeCapabilities().prehideMenuDuringPauseTransition
        && g_menuElement
        && g_renderTarget
        && g_gameplayHudSnapshot.captured;
}
'''
runtime = replace_once(runtime, old_prehide, new_prehide, "entry prehide capability")
runtime = runtime.replace("Steam Clean Pause entry render prehide", "profile Clean Pause entry render prehide")

old_deferred_guard = '''bool TryInstallDeferredPauseBarrier()
{
    if (g_pauseGameTarget || !g_activeBuildProfile || !g_environment
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam)
        return g_pauseGameTarget != nullptr;
'''
new_deferred_guard = '''bool TryInstallDeferredPauseBarrier()
{
    if (g_pauseGameTarget || !g_activeBuildProfile || !g_environment
        || !ActiveRuntimeCapabilities().deferPauseBarrierUntilPauseInput)
        return g_pauseGameTarget != nullptr;
'''
runtime = replace_once(runtime, old_deferred_guard, new_deferred_guard, "deferred barrier guard")
runtime = runtime.replace(
    'Log("deferred Steam IGameFramework pause barrier became ready on pause input");',
    'Log("deferred IGameFramework pause barrier became ready on pause input; profile=%s",\n            g_activeBuildProfile ? g_activeBuildProfile->name : "<unknown>");',
    1,
)
old_should_defer = '''    if (!event || g_forwardDepth != 0 || g_pauseGameTarget
        || !g_activeBuildProfile
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam
        || (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId))
'''
new_should_defer = '''    if (!event || g_forwardDepth != 0 || g_pauseGameTarget
        || !g_activeBuildProfile
        || !ActiveRuntimeCapabilities().deferPauseBarrierUntilPauseInput
        || (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId))
'''
runtime = replace_once(runtime, old_should_defer, new_should_defer, "deferred input capability")

runtime = runtime.replace("before Steam barrier acquisition", "before deferred barrier acquisition")
runtime = runtime.replace("Acquire the optional Steam CCryAction barrier here as well", "Acquire the optional deferred framework barrier here as well")
runtime = runtime.replace("the short provisional Steam handoff", "the short provisional profile handoff")

old_filter = '''    // bubbles::EnsureHooks lazily installs the one shared CFlashUIElement::SetVisible
    // detour on the first Pause input. Register the Steam-only hud@0 root filter now,
    // before that lazy installation can occur. Xbox/GOG/Epic behavior stays unchanged.
    bubbles::SetHudRootVisibilityFilter(
        g_activeBuildProfile
            && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::Steam
        ? &ShouldSuppressProfileHudRootVisibility
        : nullptr);
'''
new_filter = '''    // bubbles::EnsureHooks lazily installs the one shared CFlashUIElement::SetVisible
    // detour on the first Pause input. Presentation quirks are profile capabilities,
    // so the shared core never branches on storefront identity.
    bubbles::SetHudRootVisibilityFilter(
        ActiveRuntimeCapabilities().pinHudRootDuringPause
        ? &ShouldSuppressProfileHudRootVisibility
        : nullptr);
'''
runtime = replace_once(runtime, old_filter, new_filter, "root filter install")

old_barrier_install = '''    if (g_activeBuildProfile
        && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::Steam) {
        Log("Steam PauseGame observer will be acquired lazily on the first Pause input; Menu/input runtime is already active");
    } else if (g_activeBuildProfile
        && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::XboxMicrosoftStore) {
        // Preserve the already runtime-tested Xbox behavior. Unlike Steam, there is
        // no second installation path racing this bootstrap attempt.
        InstallPauseBarrierHook(environment, true);
    }
'''
new_barrier_install = '''    if (g_activeBuildProfile
        && ActiveRuntimeCapabilities().deferPauseBarrierUntilPauseInput) {
        Log("%s PauseGame observer will be acquired lazily on the first Pause input; Menu/input runtime is already active",
            g_activeBuildProfile->name);
    } else if (g_activeBuildProfile
        && g_activeBuildProfile->frameworkLocator
            != kcd2::runtime::FrameworkLocatorStrategy::None) {
        InstallPauseBarrierHook(environment, true);
    }
'''
runtime = replace_once(runtime, old_barrier_install, new_barrier_install, "barrier installation policy")

# Add framework/capability diagnostics to the selected profile log.
old_profile_log = '''        "WHGame profile candidate: %s; storefront=%s identity=%s abi=%s locator=%s evidence=%s",
        profile->name,
        kcd2::runtime::StorefrontName(profile->storefront),
        kcd2::runtime::BuildIdentityStrategyName(profile->identityStrategy),
        profile->abi->name,
        kcd2::runtime::EnvironmentLocatorName(profile->environmentLocator),
        kcd2::runtime::BuildValidationName(profile->validation));
'''
new_profile_log = '''        "WHGame profile candidate: %s; storefront=%s identity=%s abi=%s envLocator=%s frameworkLocator=%s capabilities=defer:%s,rootPin:%s,menuPrehide:%s evidence=%s",
        profile->name,
        kcd2::runtime::StorefrontName(profile->storefront),
        kcd2::runtime::BuildIdentityStrategyName(profile->identityStrategy),
        profile->abi->name,
        kcd2::runtime::EnvironmentLocatorName(profile->environmentLocator),
        kcd2::runtime::FrameworkLocatorName(profile->frameworkLocator),
        profile->capabilities.deferPauseBarrierUntilPauseInput ? "yes" : "no",
        profile->capabilities.pinHudRootDuringPause ? "yes" : "no",
        profile->capabilities.prehideMenuDuringPauseTransition ? "yes" : "no",
        kcd2::runtime::BuildValidationName(profile->validation));
'''
runtime = replace_once(runtime, old_profile_log, new_profile_log, "profile diagnostics")

# The behavior portion of the runtime must no longer branch on storefront identity.
behavior_start = runtime.index("bool ResolveProfileFrameworkSingleton")
behavior_end = runtime.index("bool PollRuntimeEnvironment", behavior_start)
behavior = runtime[behavior_start:behavior_end]
for forbidden in (
    "Storefront::Steam",
    "Storefront::XboxMicrosoftStore",
    "Storefront::GOG",
    "Storefront::EpicGamesStore",
):
    if forbidden in behavior:
        raise RuntimeError(f"storefront branch survived shared runtime behavior: {forbidden}")

RUNTIME.write_text(runtime, encoding="utf-8")


# ---------------------------------------------------------------------------
# Update source-contract tests mechanically for generalized names, then tighten
# the profile/capability expectations where storefront branching used to be tested.
# ---------------------------------------------------------------------------
for path in (TEST_PROFILE, TEST_VISIBLE, TEST_STEAM_NAME, TEST_PAUSE, VALIDATE):
    text = path.read_text(encoding="utf-8")
    for old, new in (
        ("ResolveSteamFrameworkSingleton", "ResolveProfileFrameworkSingleton"),
        ("ShouldSuppressSteamHudRootVisibility", "ShouldSuppressProfileHudRootVisibility"),
        ("ShouldPrehideSteamEntryRender", "ShouldPrehideEntryRender"),
        ("RollBackSteamEntryRenderPrehide", "RollBackEntryRenderPrehide"),
        ("g_steamEntryRenderPrehide", "g_entryRenderPrehide"),
        ("TryInstallDeferredSteamPauseBarrier", "TryInstallDeferredPauseBarrier"),
        ("ShouldTryDeferredSteamPauseBarrier", "ShouldTryDeferredPauseBarrier"),
        ("Steam Clean Pause entry render prehide", "profile Clean Pause entry render prehide"),
        ("deferred Steam IGameFramework pause barrier", "deferred IGameFramework pause barrier"),
    ):
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")

# Runtime profile source contract: framework/capability data must be first-class,
# and behavior must dispatch by framework strategy rather than storefront.
test = TEST_PROFILE.read_text(encoding="utf-8")
test = test.replace(
    '        self.assertIn("EnvironmentLocatorStrategy environmentLocator", PROFILE_H)\n        self.assertIn("const AbiProfile* abi", PROFILE_H)\n',
    '        self.assertIn("EnvironmentLocatorStrategy environmentLocator", PROFILE_H)\n        self.assertIn("FrameworkLocatorStrategy frameworkLocator", PROFILE_H)\n        self.assertIn("RuntimeCapabilities capabilities", PROFILE_H)\n        self.assertIn("const AbiProfile* abi", PROFILE_H)\n',
)
old_steam_test = '''    def test_steam_framework_uses_canonical_ccryaction_singleton(self):
        resolver = RUNTIME[
            RUNTIME.index("bool ResolveProfileFrameworkSingleton"):
            RUNTIME.index("bool ResolveGameFramework")
        ]
        self.assertIn("kSteam156FrameworkStorageRva = 0x0549D328", RUNTIME)
        self.assertIn("kSteam156FrameworkVtableRva = 0x040472D0", RUNTIME)
        self.assertIn("kGameFrameworkPauseGameSlot", resolver)
        self.assertIn("kGameFrameworkGetSystemSlot", resolver)
        self.assertIn("frameworkSystem != environment.system", resolver)
        self.assertNotIn("kGameGetFrameworkSlot", resolver)
'''
new_steam_test = '''    def test_framework_singleton_is_profile_data_not_storefront_logic(self):
        resolver = RUNTIME[
            RUNTIME.index("bool ResolveProfileFrameworkSingleton"):
            RUNTIME.index("bool ResolveGameFramework")
        ]
        self.assertIn("FrameworkLocatorStrategy::ExactSingletonRva", PROFILE)
        self.assertIn("0x0549d328", PROFILE.lower())
        self.assertIn("0x040472d0", PROFILE.lower())
        self.assertIn("expectedFrameworkStorageRva", resolver)
        self.assertIn("expectedFrameworkVtableRva", resolver)
        self.assertIn("kGameFrameworkPauseGameSlot", resolver)
        self.assertIn("kGameFrameworkGetSystemSlot", resolver)
        self.assertIn("frameworkSystem != environment.system", resolver)
        self.assertNotIn("Storefront::Steam", resolver)
        self.assertNotIn("kGameGetFrameworkSlot", resolver)
'''
if old_steam_test not in test:
    raise RuntimeError("steam framework source contract block not found")
test = test.replace(old_steam_test, new_steam_test)

test = test.replace(
    '        self.assertIn("Storefront::XboxMicrosoftStore", install)\n        self.assertIn("Storefront::Steam", install)\n',
    '        self.assertIn("FrameworkLocatorStrategy::None", install)\n        self.assertIn("deferPauseBarrierUntilPauseInput", install)\n',
)
test = test.replace(
    '        self.assertIn("Storefront::Steam", retry)\n',
    '        self.assertIn("deferPauseBarrierUntilPauseInput", retry)\n        self.assertNotIn("Storefront::Steam", retry)\n',
)
# The old branch slice by storefront no longer exists; assert the install policy directly.
old_slice = '''        install = RUNTIME[
            RUNTIME.index("bool InstallInputHook"):
            RUNTIME.index("bool PollRuntimeEnvironment")
        ]
        steam_branch = install[
            install.index("Storefront::Steam"):
            install.index("Storefront::XboxMicrosoftStore")
        ]
        self.assertNotIn("InstallPauseBarrierHook", steam_branch)
        self.assertIn("will be acquired lazily on the first Pause input", steam_branch)
'''
new_slice = '''        install = RUNTIME[
            RUNTIME.index("bool InstallInputHook"):
            RUNTIME.index("bool PollRuntimeEnvironment")
        ]
        self.assertIn("deferPauseBarrierUntilPauseInput", install)
        self.assertIn("FrameworkLocatorStrategy::None", install)
        self.assertIn("will be acquired lazily on the first Pause input", install)
        self.assertNotIn("Storefront::Steam", install)
        self.assertNotIn("Storefront::XboxMicrosoftStore", install)
'''
if old_slice not in test:
    raise RuntimeError("old Steam install slice not found")
test = test.replace(old_slice, new_slice)

old_non_xbox = '''    def test_non_xbox_profiles_never_fallback_to_igame_slot16(self):
        resolver = RUNTIME[
            RUNTIME.index("bool ResolveGameFramework"):
            RUNTIME.index("void __fastcall HookPauseGameProfiled")
        ]
        self.assertIn("Storefront::Steam", resolver)
        self.assertIn("Storefront::XboxMicrosoftStore", resolver)
        self.assertIn("LegacyResolveGameFramework_Xbox156Only", resolver)
        self.assertNotIn("kGameGetFrameworkSlot", resolver)
'''
new_non_xbox = '''    def test_framework_dispatch_is_strategy_driven(self):
        resolver = RUNTIME[
            RUNTIME.index("bool ResolveGameFramework"):
            RUNTIME.index("bool ShouldSuppressProfileHudRootVisibility")
        ]
        self.assertIn("FrameworkLocatorStrategy::ExactSingletonRva", resolver)
        self.assertIn("FrameworkLocatorStrategy::LegacyGameFrameworkSlot", resolver)
        self.assertIn("FrameworkLocatorStrategy::None", resolver)
        self.assertIn("LegacyResolveGameFramework_Xbox156Only", resolver)
        self.assertNotIn("Storefront::Steam", resolver)
        self.assertNotIn("Storefront::XboxMicrosoftStore", resolver)
        self.assertNotIn("kGameGetFrameworkSlot", resolver)
'''
if old_non_xbox not in test:
    raise RuntimeError("old framework dispatch test not found")
test = test.replace(old_non_xbox, new_non_xbox)
TEST_PROFILE.write_text(test, encoding="utf-8")

# Native executable tests lock profile data/capabilities.
native_test = NATIVE_TEST.read_text(encoding="utf-8")
native_test = native_test.replace(
    '    CHECK(steam->abi == &kcd2::runtime::Release15AbiProfile());\n',
    '''    CHECK(steam->frameworkLocator
        == kcd2::runtime::FrameworkLocatorStrategy::ExactSingletonRva);
    CHECK(steam->expectedFrameworkStorageRva == 0x0549d328);
    CHECK(steam->expectedFrameworkVtableRva == 0x040472d0);
    CHECK(steam->capabilities.deferPauseBarrierUntilPauseInput);
    CHECK(steam->capabilities.pinHudRootDuringPause);
    CHECK(steam->capabilities.prehideMenuDuringPauseTransition);
    CHECK(steam->abi == &kcd2::runtime::Release15AbiProfile());
''',
)
native_test = native_test.replace(
    '    CHECK(xboxProfile->validation == kcd2::runtime::BuildValidationLevel::RuntimeTested);\n',
    '''    CHECK(xboxProfile->frameworkLocator
        == kcd2::runtime::FrameworkLocatorStrategy::LegacyGameFrameworkSlot);
    CHECK(!xboxProfile->capabilities.deferPauseBarrierUntilPauseInput);
    CHECK(!xboxProfile->capabilities.pinHudRootDuringPause);
    CHECK(!xboxProfile->capabilities.prehideMenuDuringPauseTransition);
    CHECK(xboxProfile->validation == kcd2::runtime::BuildValidationLevel::RuntimeTested);
''',
)
native_test = native_test.replace(
    '    CHECK(gogProfile->validation == kcd2::runtime::BuildValidationLevel::ExternalRuntimeEvidence);\n',
    '''    CHECK(gogProfile->frameworkLocator == kcd2::runtime::FrameworkLocatorStrategy::None);
    CHECK(gogProfile->validation == kcd2::runtime::BuildValidationLevel::ExternalRuntimeEvidence);
''',
)
native_test = native_test.replace(
    '    CHECK(epicProfile->expectedEnvironmentRva == 0x0491d8b8);\n',
    '''    CHECK(epicProfile->expectedEnvironmentRva == 0x0491d8b8);
    CHECK(epicProfile->frameworkLocator == kcd2::runtime::FrameworkLocatorStrategy::None);
''',
)
NATIVE_TEST.write_text(native_test, encoding="utf-8")

print("runtime capability refactor applied")
