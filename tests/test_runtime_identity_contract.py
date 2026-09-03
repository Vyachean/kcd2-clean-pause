import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class RuntimeIdentityContractTests(unittest.TestCase):
    def test_runtime_identity_is_derived_from_version_and_git_head(self):
        self.assertIn('../VERSION', CMAKE)
        self.assertIn('rev-parse --short=12 HEAD', CMAKE)
        self.assertIn('CLEAN_PAUSE_VERSION="${CLEAN_PAUSE_VERSION}"', CMAKE)
        self.assertIn('CLEAN_PAUSE_BUILD_ID="${CLEAN_PAUSE_BUILD_ID}"', CMAKE)
        self.assertIn('CLEAN_PAUSE_VERSION', NATIVE)
        self.assertIn('CLEAN_PAUSE_BUILD_ID', NATIVE)
        self.assertNotIn('KCD2 Clean Pause v0.1.0 active', NATIVE)
        self.assertNotIn('KCD2 Clean Pause v0.1.0")', NATIVE)


if __name__ == '__main__':
    unittest.main()
