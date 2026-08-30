import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")
ASI_ENTRY = (ROOT / "native/src/asi_entry.cpp").read_text(encoding="utf-8")
VERSION_ENTRY = (ROOT / "native/src/version_proxy.cpp").read_text(encoding="utf-8")
PROCESS_GUARD = (ROOT / "native/src/process_guard.cpp").read_text(encoding="utf-8")
RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
ASI_INSTALL = (ROOT / "native/INSTALL_ASI.txt").read_text(encoding="utf-8")
NOTICES = (ROOT / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")


class DualPackageContractTests(unittest.TestCase):
    def test_both_editions_compile_the_same_runtime(self):
        self.assertIn("set(CLEAN_PAUSE_RUNTIME_SOURCES", CMAKE)
        self.assertIn("add_library(kcd2_clean_pause_version SHARED", CMAKE)
        self.assertIn("add_library(kcd2_clean_pause_asi SHARED", CMAKE)
        self.assertGreaterEqual(CMAKE.count("${CLEAN_PAUSE_RUNTIME_SOURCES}"), 2)
        self.assertIn("src/process_guard.cpp", CMAKE)

    def test_asi_entry_only_bootstraps_clean_pause(self):
        self.assertIn("clean_pause::AcquireProcessGuard()", ASI_ENTRY)
        self.assertIn("clean_pause::Start(instance);", ASI_ENTRY)
        self.assertIn("clean_pause::Stop();", ASI_ENTRY)
        self.assertNotIn("LoadLibraryW", ASI_ENTRY)
        self.assertNotIn("GetFileVersionInfo", ASI_ENTRY)

    def test_version_proxy_keeps_windows_forwarding(self):
        self.assertIn('path += L"\\\\version.dll";', VERSION_ENTRY)
        self.assertIn("Proxy_GetFileVersionInfoW", VERSION_ENTRY)
        self.assertIn("Proxy_VerQueryValueW", VERSION_ENTRY)
        self.assertIn("clean_pause::AcquireProcessGuard()", VERSION_ENTRY)
        self.assertIn("clean_pause::Start(instance);", VERSION_ENTRY)

    def test_double_load_guard_is_process_scoped(self):
        self.assertIn("GetCurrentProcessId()", PROCESS_GUARD)
        self.assertIn("CreateMutexW", PROCESS_GUARD)
        self.assertIn("ERROR_ALREADY_EXISTS", PROCESS_GUARD)
        self.assertIn("CloseHandle(guard);", PROCESS_GUARD)

    def test_release_validates_both_editions_but_publishes_only_allowed_assets(self):
        self.assertIn("KCD2CleanPause.asi", RELEASE)
        self.assertIn("version.dll", RELEASE)
        self.assertIn("-asi.zip", RELEASE)
        self.assertIn("-version-dll.zip", RELEASE)
        self.assertIn("INSTALL_ASI.txt", RELEASE)
        self.assertIn("INSTALL_VERSION_DLL.txt", RELEASE)
        self.assertIn("CI_SHA256SUMS.txt", RELEASE)
        self.assertIn("SHA256SUMS.txt", RELEASE)
        publish = RELEASE[RELEASE.index("- name: Publish GitHub Release") :]
        self.assertIn('"release/$ASI_ASSET" "release/SHA256SUMS.txt"', publish)
        self.assertNotIn("VERSION_ASSET", publish)
        self.assertGreaterEqual(RELEASE.count("THIRD_PARTY_NOTICES.txt"), 5)
        self.assertIn("MinHook v1.3.4", NOTICES)
        self.assertIn("Copyright (C) 2009-2017 Tsuda Kageyu.", NOTICES)
        self.assertIn("Redistributions in binary form must reproduce", NOTICES)

    def test_asi_release_bundles_pinned_official_loader(self):
        self.assertIn("ULTIMATE_ASI_LOADER_VERSION: v9.7.4", RELEASE)
        self.assertIn(
            "ULTIMATE_ASI_LOADER_COMMIT: 6b440669144c4a0bef5718ab155df160d231cd42",
            RELEASE,
        )
        self.assertIn(
            "ULTIMATE_ASI_LOADER_ASSET: Ultimate-ASI-Loader_x64.zip",
            RELEASE,
        )
        self.assertIn(
            "ULTIMATE_ASI_LOADER_SHA256: 8272d83b2692662098746f2d0ad0e2d85f3c8358ab1d63f75fbe835c2c8135fd",
            RELEASE,
        )
        self.assertNotIn("releases/latest", RELEASE)
        self.assertIn("ThirteenAG/Ultimate-ASI-Loader/releases/download/", RELEASE)
        self.assertIn("Get-FileHash $loaderArchive -Algorithm SHA256", RELEASE)
        self.assertIn("$loaderArchiveHash -ne $env:ULTIMATE_ASI_LOADER_SHA256", RELEASE)
        self.assertIn('Get-ChildItem $loaderExtract -Recurse -File -Filter "dinput8.dll"', RELEASE)
        self.assertIn('Copy-Item $loader release/asi/dinput8.dll', RELEASE)
        self.assertIn('machine \\(x64\\)', RELEASE)

    def test_asi_release_carries_loader_provenance_and_license(self):
        self.assertIn("ASI_LOADER_SOURCE.txt", RELEASE)
        self.assertIn("ULTIMATE_ASI_LOADER_LICENSE.txt", RELEASE)
        self.assertIn("raw.githubusercontent.com/ThirteenAG/Ultimate-ASI-Loader/", RELEASE)
        self.assertIn("Source commit:", RELEASE)
        self.assertIn("Bundled file SHA-256:", RELEASE)
        self.assertIn("Ultimate ASI Loader", NOTICES)
        self.assertIn("MIT License", NOTICES)

    def test_asi_install_supports_fresh_and_shared_loader_installations(self):
        self.assertIn("includes the retail-tested x64 Ultimate ASI Loader", ASI_INSTALL)
        self.assertIn("Copy both dinput8.dll and KCD2CleanPause.asi", ASI_INSTALL)
        self.assertIn("do not overwrite it blindly", ASI_INSTALL)
        self.assertIn("where that existing ASI loader actually searches for plugins", ASI_INSTALL)
        self.assertIn("place KCD2CleanPause.asi beside the existing dinput8.dll", ASI_INSTALL)
        self.assertIn("scripts/ and plugins/ directories", ASI_INSTALL)
        self.assertIn("unless that loader is explicitly configured to scan the latter location", ASI_INSTALL)


if __name__ == "__main__":
    unittest.main()
