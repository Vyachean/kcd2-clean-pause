import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")
ASI_ENTRY = (ROOT / "native/src/asi_entry.cpp").read_text(encoding="utf-8")
VERSION_ENTRY = (ROOT / "native/src/version_proxy.cpp").read_text(encoding="utf-8")
RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")


class DualPackageContractTests(unittest.TestCase):
    def test_both_editions_compile_the_same_runtime(self):
        self.assertIn("set(CLEAN_PAUSE_RUNTIME_SOURCES", CMAKE)
        self.assertIn("add_library(kcd2_clean_pause_version SHARED", CMAKE)
        self.assertIn("add_library(kcd2_clean_pause_asi SHARED", CMAKE)
        self.assertGreaterEqual(CMAKE.count("${CLEAN_PAUSE_RUNTIME_SOURCES}"), 2)

    def test_asi_entry_only_bootstraps_clean_pause(self):
        self.assertIn("clean_pause::Start(instance);", ASI_ENTRY)
        self.assertIn("clean_pause::Stop();", ASI_ENTRY)
        self.assertNotIn("LoadLibraryW", ASI_ENTRY)
        self.assertNotIn("GetFileVersionInfo", ASI_ENTRY)

    def test_version_proxy_keeps_windows_forwarding(self):
        self.assertIn('path += L"\\\\version.dll";', VERSION_ENTRY)
        self.assertIn("Proxy_GetFileVersionInfoW", VERSION_ENTRY)
        self.assertIn("Proxy_VerQueryValueW", VERSION_ENTRY)
        self.assertIn("clean_pause::Start(instance);", VERSION_ENTRY)

    def test_release_publishes_two_mutually_exclusive_assets(self):
        self.assertIn("KCD2CleanPause.asi", RELEASE)
        self.assertIn("version.dll", RELEASE)
        self.assertIn("-asi.zip", RELEASE)
        self.assertIn("-version-dll.zip", RELEASE)
        self.assertIn("INSTALL_ASI.txt", RELEASE)
        self.assertIn("INSTALL_VERSION_DLL.txt", RELEASE)
        self.assertIn("SHA256SUMS.txt", RELEASE)


if __name__ == "__main__":
    unittest.main()
