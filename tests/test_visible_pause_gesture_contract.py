import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILED = (ROOT / "native/src/clean_pause_native_profiled.cpp").read_text(encoding="utf-8")


class VisiblePauseGestureContractTests(unittest.TestCase):
    def test_visible_menu_is_checked_before_clean_pause_preparation(self):
        helper = PROFILED[
            PROFILED.index("bool ForwardVisiblePauseGestureIfNeeded"):
            PROFILED.index("void __fastcall HookPostInputEventProfiled")
        ]
        self.assertIn("ReadVerifiedMenuVisible", helper)
        self.assertIn("EnsureMenuRenderHook", helper)
        self.assertIn("g_visiblePauseGesturePassthrough", helper)
        self.assertIn("Forward(input, event, force);", helper)
        self.assertNotIn("CaptureHudVisibilitySnapshot", helper)
        self.assertNotIn("ResetHudSnapshots", helper)

        wrapper = PROFILED[
            PROFILED.index("void __fastcall HookPostInputEventProfiled"):
            PROFILED.index("bool InstallInputHook")
        ]
        preflight = wrapper.index("ForwardVisiblePauseGestureIfNeeded")
        deferred_barrier = wrapper.index("ShouldTryDeferredSteamPauseBarrier")
        legacy_core = wrapper.index("LegacyHookPostInputEventProfiledCore")
        self.assertLess(preflight, deferred_barrier)
        self.assertLess(preflight, legacy_core)

    def test_visible_menu_passthrough_latches_until_physical_release(self):
        helper = PROFILED[
            PROFILED.index("bool ForwardVisiblePauseGestureIfNeeded"):
            PROFILED.index("void __fastcall HookPostInputEventProfiled")
        ]
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(true, std::memory_order_release)",
            helper,
        )
        self.assertIn("if (g_visiblePauseGesturePassthrough.load", helper)
        self.assertIn("if (released)", helper)
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_release)",
            helper,
        )
        self.assertIn("visible vanilla pause menu", helper)

    def test_latch_is_reset_at_runtime_boundaries(self):
        start = PROFILED[PROFILED.index("bool Start(HMODULE selfModule)"):]
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_relaxed)",
            start,
        )
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_release)",
            start,
        )


if __name__ == "__main__":
    unittest.main()
