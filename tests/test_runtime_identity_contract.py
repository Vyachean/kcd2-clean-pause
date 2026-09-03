import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ABI = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")
PROFILED = (ROOT / "native/src/clean_pause_native_profiled.cpp").read_text(encoding="utf-8")


class RuntimeIdentityContractTests(unittest.TestCase):
    def test_only_observed_game_name_spellings_are_accepted(self):
        self.assertIn('std::strcmp(gameName, "kcd2") == 0', PROFILED)
        self.assertIn('std::strcmp(gameName, "KCD2") == 0', PROFILED)
        self.assertIn('return "game-name-mismatch"', PROFILED)

    def test_unverified_pause_state_accessor_is_not_part_of_release15_abi(self):
        self.assertNotIn("kGameFrameworkIsGamePausedSlot", ABI)
        self.assertNotIn("IsGamePausedFn", ABI)
        self.assertIn("kGameFrameworkPauseGameSlot = 13", ABI)
        self.assertIn("kGameFrameworkGetSystemSlot = 19", ABI)


if __name__ == "__main__":
    unittest.main()
