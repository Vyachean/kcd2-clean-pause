import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = (ROOT / "native/src/kcd2_runtime_profile.cpp").read_text(encoding="utf-8")
PROFILE_H = (ROOT / "native/src/kcd2_runtime_profile.h").read_text(encoding="utf-8")
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
ABI = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class RuntimeProfileContractTests(unittest.TestCase):
    def test_supported_retail_fingerprints_are_explicit(self):
        profile = PROFILE.lower()
        self.assertIn("0x6a391f7b", profile)
        self.assertIn("0x05bf2000", profile)
        self.assertIn("0x6a350e20", profile)
        self.assertIn("0x05b2d000", profile)
        self.assertIn("xbox store 1.5.6", profile)
        self.assertIn("steam 1.5.6 release_1_5-15693", profile)

    def test_canonical_environment_uses_code_anchor_not_writable_scan(self):
        self.assertIn('"exec autoexec.cfg"', PROFILE)
        self.assertIn("ResolveUniqueConsoleStorage", PROFILE)
        self.assertIn("kEnvConsoleOffset", PROFILE)
        self.assertIn("kEnvConsoleOffset = 0xB0", ABI)
        self.assertIn("ResolveCanonicalEnvironmentBase", NATIVE)
        self.assertNotIn("for (std::size_t offset = 0; offset <= limit; offset += alignof(void*))", NATIVE)

    def test_unknown_build_is_rejected_before_runtime_discovery(self):
        bootstrap = NATIVE[NATIVE.index("DWORD WINAPI BootstrapThread"):]
        match = bootstrap.index("MatchSupportedBuild")
        discover = bootstrap.index("FindRuntimeEnvironment")
        install = bootstrap.index("InstallInputHook")
        self.assertLess(match, discover)
        self.assertLess(discover, install)
        self.assertIn("unsupported WHGame build; Clean Pause disabled; no hooks installed", bootstrap)

    def test_candidate_thread_must_belong_to_current_process(self):
        self.assertIn("GetProcessIdOfThread", NATIVE)
        self.assertIn("GetCurrentProcessId", NATIVE)

    def test_profile_sources_are_compiled_into_both_runtime_artifacts(self):
        self.assertIn("src/kcd2_runtime_profile.cpp", CMAKE)
        self.assertIn("src/kcd2_runtime_profile.h", CMAKE)
        self.assertIn("kcd2_runtime_profile.h", PROFILE_H)


if __name__ == "__main__":
    unittest.main()
