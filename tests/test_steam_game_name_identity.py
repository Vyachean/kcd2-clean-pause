import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "native/src/clean_pause_native_profiled.cpp").read_text(encoding="utf-8")


class SteamGameNameIdentityTests(unittest.TestCase):
    def test_profiled_runtime_accepts_both_observed_retail_casings(self):
        validate = BOOTSTRAP[
            BOOTSTRAP.index("const char* ValidateProfileEnvironment"):
            BOOTSTRAP.index("bool ResolveSteamFrameworkSingleton")
        ]
        self.assertIn('std::strcmp(gameName, "kcd2") == 0', validate)
        self.assertIn('std::strcmp(gameName, "KCD2") == 0', validate)
        self.assertIn('Xbox returned "kcd2"', validate)
        self.assertIn('Steam 1.5.6 release_1_5-15693 returns "KCD2"', validate)
        self.assertIn('return "game-name-mismatch";', validate)


if __name__ == "__main__":
    unittest.main()
