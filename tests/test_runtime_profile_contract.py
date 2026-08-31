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
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class RuntimeProfileContractTests(unittest.TestCase):
    def test_all_release15_store_builds_are_registered_with_evidence(self):
        profile = PROFILE.lower()
        for name in (
            "xbox / microsoft store 1.5.6",
            "steam 1.5.6 release_1_5-15693",
            "gog 1.5.6 release_1_5-15693",
            "epic games store 1.5.6 release_1_5-15693",
        ):
            self.assertIn(name, profile)
        self.assertIn("0x6a391f7b", profile)
        self.assertIn("0x05bf2000", profile)
        self.assertIn("0x6a350e20", profile)
        self.assertIn("0x05b2d000", profile)
        self.assertIn("0x6a34f917", profile)
        self.assertIn("0x0492d7f8", profile)
        self.assertIn("0x049177f8", profile)
        self.assertIn("0x0491d8b8", profile)

    def test_all_known_pc_storefronts_are_first_class(self):
        for token in (
            "Storefront::Steam",
            "Storefront::EpicGamesStore",
            "Storefront::GOG",
            "Storefront::XboxMicrosoftStore",
        ):
            self.assertIn(token, PROFILE)
        self.assertIn("enum class Storefront", PROFILE_H)
        self.assertIn("KnownStorefronts", PROFILE_H)
        self.assertIn("publicRelease15AddressLibrary", PROFILE_H)

    def test_build_identity_storefront_locator_and_abi_are_separate_dimensions(self):
        self.assertIn("enum class BuildIdentityStrategy", PROFILE_H)
        self.assertIn("ExactPeFingerprint", PROFILE_H)
        self.assertIn("StorefrontBuildCode", PROFILE_H)
        self.assertIn("Storefront storefront", PROFILE_H)
        self.assertIn("BuildIdentityStrategy identityStrategy", PROFILE_H)
        self.assertIn("Fingerprint exactFingerprint", PROFILE_H)
        self.assertIn("const char* buildCode", PROFILE_H)
        self.assertIn("expectedEnvironmentRva", PROFILE_H)
        self.assertIn("EnvironmentLocatorStrategy environmentLocator", PROFILE_H)
        self.assertIn("const AbiProfile* abi", PROFILE_H)
        self.assertNotIn("StorefrontProfile", PROFILE_H)
        self.assertIn("switch (profile.environmentLocator)", BOOTSTRAP)
        self.assertIn("MatureRuntimeSupports(*profile->abi)", BOOTSTRAP)

    def test_gog_and_epic_use_independent_distribution_build_and_rva_evidence(self):
        self.assertIn('"steam_api64.dll"', PROFILE)
        self.assertIn('"Galaxy64.dll"', PROFILE)
        self.assertIn('"EOSSDK-Win64-Shipping.dll"', PROFILE)
        self.assertIn('FindAsciiInSection(image, ".rdata", marker.text)', PROFILE)
        self.assertIn("whdlversions.json", PROFILE)
        self.assertIn('branch + "-" + assemblyId', PROFILE)
        self.assertIn("ParseWarhorseBuildCode", PROFILE)
        self.assertIn("ReadBuildCodeFromModulePath", PROFILE)
        self.assertGreaterEqual(PROFILE.count('"release_1_5-15693"'), 3)
        self.assertIn("BuildIdentityStrategy::StorefrontBuildCode", PROFILE)
        self.assertIn("EnvironmentLocatorStrategy::ExactEnvironmentRva", PROFILE)
        self.assertIn("profile.expectedEnvironmentRva", PROFILE)

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

    def test_profiled_non_xbox_environment_resolution_is_one_time_and_evidence_specific(self):
        self.assertIn("EnvironmentLocatorStrategy::ExactEnvironmentRva", PROFILE)
        self.assertIn("EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation", PROFILE)
        self.assertIn('"exec autoexec.cfg"', PROFILE)
        self.assertIn("ResolveUniqueConsoleStorage", PROFILE)
        self.assertIn("ResolveProfileEnvironmentBase", PROFILE)
        self.assertIn("image.base + environmentRva", PROFILE)
        self.assertIn("anchorConsoleStorage != expectedConsoleStorage", PROFILE)

        marker = "DWORD WINAPI BootstrapThread(void*)"
        bootstrap = BOOTSTRAP[BOOTSTRAP.index(marker):]
        self.assertEqual(bootstrap.count("ResolveProfileEnvironmentBase("), 1)
        resolve = bootstrap.index("ResolveProfileEnvironmentBase")
        poll_loop = bootstrap.index("for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs")
        self.assertLess(resolve, poll_loop)
        self.assertIn("PollRuntimeEnvironment", bootstrap[poll_loop:])
        self.assertNotIn("ResolveProfileEnvironmentBase", bootstrap[poll_loop:])

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
        read_identity = bootstrap.index("ReadBuildIdentity")
        match = bootstrap.index("MatchSupportedBuild")
        abi_gate = bootstrap.index("MatureRuntimeSupports")
        resolve = bootstrap.index("ResolveProfileEnvironmentBase")
        poll = bootstrap.index("PollRuntimeEnvironment")
        install = bootstrap.index("InstallInputHook")
        self.assertLess(read_identity, match)
        self.assertLess(match, abi_gate)
        self.assertLess(abi_gate, resolve)
        self.assertLess(resolve, poll)
        self.assertLess(poll, install)
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
        self.assertIn("ResolveProfileEnvironmentBase", PROFILE_H)


if __name__ == "__main__":
    unittest.main()
