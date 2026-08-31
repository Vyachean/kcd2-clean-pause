import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")
PROBE = (ROOT / "native/src/steam_runtime_probe.cpp").read_text(encoding="utf-8")
PROBE_ENTRY = (ROOT / "native/src/steam_probe_entry.cpp").read_text(encoding="utf-8")
VALIDATE = (ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")


class SteamRuntimeProbeTests(unittest.TestCase):
    def test_probe_is_a_separate_diagnostic_artifact(self):
        self.assertIn("kcd2_clean_pause_steam_probe", CMAKE)
        self.assertIn('OUTPUT_NAME "KCD2CleanPauseSteamProbe"', CMAKE)
        self.assertIn("steam_probe_entry.cpp", CMAKE)
        self.assertIn("steam_runtime_probe.cpp", CMAKE)
        self.assertIn("clean_pause::steam_probe::Start(instance);", PROBE_ENTRY)
        self.assertNotIn("clean_pause::Start(instance);", PROBE_ENTRY)

    def test_probe_installs_no_hooks(self):
        self.assertNotIn("MH_CreateHook", PROBE)
        self.assertNotIn("MH_EnableHook", PROBE)
        self.assertNotIn("VirtualProtect", PROBE)
        self.assertIn("no hooks will be installed", PROBE)
        self.assertIn("probe complete; no hooks were installed", PROBE)

    def test_probe_uses_reported_steam_fingerprint_and_anchor(self):
        self.assertIn("0x6a350e20", PROBE)
        self.assertIn("0x05b2d000", PROBE)
        self.assertIn('FindAscii(image, "exec autoexec.cfg")', PROBE)
        self.assertIn("ResolveConsoleFieldStorage", PROBE)
        self.assertIn("kSteamConsoleOffset = 0xA8", PROBE)

    def test_probe_checks_interface_identity_without_enabling_runtime(self):
        self.assertIn("IGame identity:", PROBE)
        self.assertIn("IGame::GetIGameFramework", PROBE)
        self.assertIn("IGameFramework identity: GetISystem", PROBE)
        self.assertIn("LogThreadIdCandidates", PROBE)
        self.assertIn("pFlashUI[standard-hypothesis]", PROBE)

    def test_ci_builds_and_uploads_probe(self):
        self.assertIn("KCD2CleanPauseSteamProbe.asi", VALIDATE)
        self.assertGreaterEqual(VALIDATE.count("$steamProbe"), 2)


if __name__ == "__main__":
    unittest.main()
