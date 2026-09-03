import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")


class GameplayHudSnapshotFastPathTests(unittest.TestCase):
    def test_internal_mask_is_primary_gameplay_snapshot_source(self):
        helper = NATIVE[
            NATIVE.index("bool CaptureGameplayHudSnapshot()"):
            NATIVE.index("bool RestoreVanillaHudPresentation")
        ]
        self.assertIn("g_hudMaskTransactionAvailable.load", helper)
        self.assertIn("CaptureVanillaHudFromInternalMask(current)", helper)
        self.assertIn("g_gameplayHudSnapshot = current", helper)
        self.assertIn(
            'CaptureHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-pre-pause")',
            helper,
        )

        fast = helper.index("CaptureVanillaHudFromInternalMask(current)")
        fallback = helper.index("CaptureHudVisibilitySnapshot(g_gameplayHudSnapshot")
        self.assertLess(fast, fallback)

    def test_physical_pause_path_no_longer_walks_28_flash_clips_directly(self):
        hook = NATIVE[
            NATIVE.index("void __fastcall HookPostInputEvent"):
            NATIVE.index("bool ResolveGameFramework")
        ]
        self.assertIn("CaptureGameplayHudSnapshot()", hook)
        self.assertNotIn(
            'CaptureHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-pre-pause")',
            hook,
        )

    def test_internal_snapshot_keeps_root_and_all_mask_flags(self):
        helper = NATIVE[
            NATIVE.index("bool CaptureVanillaHudFromInternalMask"):
            NATIVE.index("bool CaptureGameplayHudSnapshot")
        ]
        self.assertIn("hud_mask::ReadCurrentVisibility", helper)
        self.assertIn("kHudClipCount", helper)
        self.assertIn("target.visible[i] = visible[i]", helper)
        self.assertIn("target.rootVisible = rootVisible", helper)
        self.assertIn("target.captured = true", helper)


if __name__ == "__main__":
    unittest.main()
