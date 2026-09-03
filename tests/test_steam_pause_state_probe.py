import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABI = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")
PROBE = (ROOT / "native/src/steam_pause_state_probe.cpp").read_text(encoding="utf-8")
ASI_ENTRY = (ROOT / "native/src/asi_entry.cpp").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class SteamPauseStateProbeTests(unittest.TestCase):
    def test_release15_exposes_optional_is_game_paused_diagnostic_slot(self):
        self.assertIn("kGameFrameworkPauseGameSlot = 13", ABI)
        self.assertIn("kGameFrameworkIsGamePausedSlot = 14", ABI)
        self.assertIn("kGameFrameworkGetSystemSlot = 19", ABI)
        self.assertIn("using IsGamePausedFn = bool(__fastcall*)(void*)", ABI)
        self.assertIn("must confirm this accessor before it becomes a required ABI gate", ABI)

    def test_probe_is_exact_steam156_and_strongly_identifies_framework(self):
        for needle in (
            "kSteam156Timestamp = 0x6a350e20",
            "kSteam156ImageSize = 0x05b2d000",
            "kSteam156EnvironmentRva = 0x0492D7F8",
            "kSteam156FrameworkStorageRva = 0x0549D328",
            "kSteam156FrameworkVtableRva = 0x040472D0",
            "kGameFrameworkGetSystemSlot",
            "actualSystem != expectedSystem",
        ):
            self.assertIn(needle, PROBE)

    def test_probe_observes_getter_without_changing_return_value(self):
        hook = PROBE[
            PROBE.index("bool __fastcall HookIsGamePaused"):
            PROBE.index("bool InstallObserver")
        ]
        self.assertIn("const bool paused = g_originalIsGamePaused(framework);", hook)
        self.assertIn("g_lastPausedState.exchange", hook)
        self.assertIn("if (previous != next)", hook)
        self.assertIn("return paused;", hook)
        self.assertNotIn("PauseGameFn", hook)

    def test_probe_does_not_compete_with_clean_pause_pausegame_hook(self):
        self.assertNotIn("kGameFrameworkPauseGameSlot", PROBE)
        self.assertNotIn("HookPauseGame", PROBE)
        self.assertIn("kGameFrameworkIsGamePausedSlot", PROBE)

    def test_probe_is_temporary_asi_only_diagnostic(self):
        self.assertIn("StartSteamPauseStateProbe(instance)", ASI_ENTRY)
        self.assertIn("StopSteamPauseStateProbe()", ASI_ENTRY)
        asi = CMAKE[
            CMAKE.index("add_library(kcd2_clean_pause_asi SHARED"):
            CMAKE.index("if(CLEAN_PAUSE_BUILD_RUNTIME_TESTS)")
        ]
        version = CMAKE[
            CMAKE.index("add_library(kcd2_clean_pause_version SHARED"):
            CMAKE.index("add_library(kcd2_clean_pause_asi SHARED")
        ]
        self.assertIn("src/steam_pause_state_probe.cpp", asi)
        self.assertNotIn("src/steam_pause_state_probe.cpp", version)


if __name__ == "__main__":
    unittest.main()
