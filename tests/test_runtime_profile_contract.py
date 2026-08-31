import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = (ROOT / "native/src/kcd2_runtime_profile.cpp").read_text(encoding="utf-8")
PROFILE_H = (ROOT / "native/src/kcd2_runtime_profile.h").read_text(encoding="utf-8")
ABI_PROFILE = (ROOT / "native/src/kcd2_abi_profile.cpp").read_text(encoding="utf-8")
ABI_PROFILE_H = (ROOT / "native/src/kcd2_abi_profile.h").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "native/src/clean_pause_native_profiled.cpp").read_text(encoding="utf-8")
LEGACY = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
BUBBLES = (ROOT / "native/src/clean_pause_bubbles.cpp").read_text(encoding="utf-8")
HUD_MASK = (ROOT / "native/src/clean_pause_hud_mask.cpp").read_text(encoding="utf-8")
ABI = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class RuntimeProfileContractTests(unittest.TestCase):
    def test_supported_retail_fingerprints_are_explicit(self):
        profile = PROFILE.lower()
        self.assertIn("0x6a391f7b", profile)
        self.assertIn("0x05bf2000", profile)
        self.assertIn("0x6a350e20", profile)
        self.assertIn("0x05b2d000", profile)
        self.assertIn("xbox / microsoft store 1.5.6", profile)
        self.assertIn("steam 1.5.6 release_1_5-15693", profile)

    def test_all_known_pc_storefronts_are_first_class(self):
        for token in (
            "Storefront::Steam",
            "Storefront::EpicGamesStore",
            "Storefront::GOG",
            "Storefront::XboxMicrosoftStore",
        ):
            self.assertIn(token, PROFILE)
        self.assertIn("enum class Storefront", PROFILE_H)
        self.assertIn("Steam", PROFILE_H)
        self.assertIn("EpicGamesStore", PROFILE_H)
        self.assertIn("GOG", PROFILE_H)
        self.assertIn("XboxMicrosoftStore", PROFILE_H)
        self.assertIn("KnownStorefronts", PROFILE_H)
        self.assertIn("publicRelease15AddressLibrary", PROFILE_H)

    def test_build_storefront_locator_and_abi_are_separate_dimensions(self):
        self.assertIn("Storefront storefront", PROFILE_H)
        self.assertIn("EnvironmentLocatorStrategy environmentLocator", PROFILE_H)
        self.assertIn("const AbiProfile* abi", PROFILE_H)
        self.assertIn("BuildValidationLevel validation", PROFILE_H)
        self.assertNotIn("StorefrontProfile", PROFILE_H)
        self.assertNotIn("switch (profile.id)", BOOTSTRAP)
        self.assertIn("switch (profile.environmentLocator)", BOOTSTRAP)
        self.assertIn("MatureRuntimeSupports(*profile->abi)", BOOTSTRAP)

    def test_release15_abi_profile_captures_runtime_binary_contract(self):
        self.assertIn("struct EnvironmentLayout", ABI_PROFILE_H)
        self.assertIn("struct VtableLayout", ABI_PROFILE_H)
        self.assertIn("struct InputLayout", ABI_PROFILE_H)
        self.assertIn("struct PresentationLayout", ABI_PROFILE_H)
        self.assertIn("struct AbiProfile", ABI_PROFILE_H)
        self.assertIn("KCD2 release_1_5 / 1.5.6 ABI", ABI_PROFILE)
        self.assertIn("MatureRuntimeSupports", ABI_PROFILE)
        self.assertIn("presentation.hudListenersOffset == 0x1D0", ABI_PROFILE)
        self.assertIn("presentation.maskSourceMonitorOffset == 0x60", ABI_PROFILE)
        self.assertIn("input.size != sizeof(InputEvent)", ABI_PROFILE)

    def test_mature_presentation_adapter_literals_stay_in_sync_with_profile(self):
        for source in (BUBBLES, HUD_MASK):
            self.assertIn("kHudListenersOffset = 0x1D0", source)
        self.assertIn("kBubbleListenerOffset = 0x10", BUBBLES)
        self.assertIn("kBubbleInterfaceOffset = 0x58", BUBBLES)
        self.assertIn("kBubbleUpdateSlot = 1", BUBBLES)
        self.assertIn("kBubbleReleaseSlot = 3", BUBBLES)
        self.assertIn("kMaskListenerOffset = 0x10", HUD_MASK)
        self.assertIn("kMaskVisibilityInterfaceOffset = 0x58", HUD_MASK)
        self.assertIn("kMaskSourceMonitorOffset = 0x60", HUD_MASK)
        self.assertIn("kMaskOnModuleMessageSlot = 3", HUD_MASK)
        self.assertIn("kMaskIsElementVisibleSlot = 1", HUD_MASK)
        self.assertIn("kModuleMessageIdOffset = 0x08", HUD_MASK)
        self.assertIn("kHudRefreshModuleMessageId = 52", HUD_MASK)
        self.assertIn("kFlashDisplayInfoSize = 0x38", LEGACY)
        self.assertIn("kFlashDisplayInfoVisibleOffset = 0x28", LEGACY)
        self.assertIn("kUIElementRenderSlot = 24", LEGACY)
        self.assertIn("kUIElementCallFunctionByNameSlot = 69", LEGACY)

    def test_steam_uses_abi_driven_canonical_anchor_discovery(self):
        self.assertIn('"exec autoexec.cfg"', PROFILE)
        self.assertIn("ResolveUniqueConsoleStorage", PROFILE)
        self.assertIn("profile.abi->environment.consoleOffset", PROFILE)
        self.assertIn("profile.abi->environment.size", PROFILE)
        self.assertIn("EnvironmentLocatorStrategy::CanonicalPConsoleCodeAnchor", BOOTSTRAP)
        self.assertIn("ResolveCanonicalEnvironmentBase", BOOTSTRAP)

    def test_xbox_legacy_discovery_is_locator_scoped(self):
        self.assertIn("LegacyFindRuntimeEnvironment_Xbox156Only", BOOTSTRAP)
        self.assertIn("EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan", BOOTSTRAP)
        self.assertIn("StronglyValidateEnvironment", BOOTSTRAP)
        self.assertNotIn("src/clean_pause_native.cpp\n", CMAKE)
        self.assertIn("src/clean_pause_native_profiled.cpp", CMAKE)
        self.assertIn("for (std::size_t offset = 0; offset <= limit", LEGACY)

    def test_unknown_build_is_rejected_before_abi_or_runtime_discovery(self):
        marker = "DWORD WINAPI BootstrapThread(void*)"
        bootstrap = BOOTSTRAP[BOOTSTRAP.index(marker):]
        match = bootstrap.index("MatchSupportedBuild")
        abi_gate = bootstrap.index("MatureRuntimeSupports")
        discover = bootstrap.index("FindRuntimeEnvironment")
        install = bootstrap.index("InstallInputHook")
        self.assertLess(match, abi_gate)
        self.assertLess(abi_gate, discover)
        self.assertLess(discover, install)
        self.assertIn("unsupported WHGame build; Clean Pause disabled; no hooks installed", bootstrap)

    def test_candidate_identity_is_strongly_validated(self):
        self.assertIn("GetProcessIdOfThread", BOOTSTRAP)
        self.assertIn("GetCurrentProcessId", BOOTSTRAP)
        self.assertIn('std::strcmp(gameName, "kcd2") == 0', BOOTSTRAP)
        self.assertIn("frameworkSystem == environment.system", BOOTSTRAP)

    def test_profile_sources_are_compiled_into_both_runtime_artifacts(self):
        self.assertIn("src/kcd2_abi_profile.cpp", CMAKE)
        self.assertIn("src/kcd2_abi_profile.h", CMAKE)
        self.assertIn("src/kcd2_runtime_profile.cpp", CMAKE)
        self.assertIn("src/kcd2_runtime_profile.h", CMAKE)
        self.assertIn("ResolveCanonicalEnvironmentBase", PROFILE_H)
        self.assertIn("kcd2_abi_profile.cpp", CMAKE)


if __name__ == "__main__":
    unittest.main()
