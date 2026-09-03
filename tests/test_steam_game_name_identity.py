import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABI = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")
RUNTIME = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")


class SteamGameNameIdentityTests(unittest.TestCase):
    def test_profiled_runtime_accepts_both_observed_retail_casings(self):
        validate = RUNTIME[
            RUNTIME.index("const char* ValidateProfileEnvironment"):
            RUNTIME.index("bool ResolveProfileFrameworkSingleton")
        ]
        self.assertIn('std::strcmp(gameName, "kcd2") == 0', validate)
        self.assertIn('std::strcmp(gameName, "KCD2") == 0', validate)
        self.assertIn('Xbox returned "kcd2"', validate)
        self.assertIn('Steam 1.5.6 release_1_5-15693 returns "KCD2"', validate)
        self.assertIn('return "game-name-mismatch";', validate)

    def test_rejected_pause_state_probe_did_not_enter_release15_abi(self):
        self.assertNotIn("kGameFrameworkIsGamePausedSlot", ABI)
        self.assertNotIn("IsGamePausedFn", ABI)
        self.assertIn("kGameFrameworkPauseGameSlot = 13", ABI)
        self.assertIn("kGameFrameworkGetSystemSlot = 19", ABI)


if __name__ == "__main__":
    unittest.main()
