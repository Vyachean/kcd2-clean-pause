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
        resume_snapshot = wrapper.index("UpdateResumeHudSnapshotForPauseInput")
        deferred_barrier = wrapper.index("ShouldTryDeferredSteamPauseBarrier")
        legacy_core = wrapper.index("LegacyHookPostInputEventProfiledCore")
        self.assertLess(preflight, resume_snapshot)
        self.assertLess(preflight, deferred_barrier)
        self.assertLess(preflight, legacy_core)

    def test_visible_menu_passthrough_latches_until_physical_release(self):
        helper = PROFILED[
            PROFILED.index("bool ForwardVisiblePauseGestureIfNeeded"):
            PROFILED.index("void __fastcall HookPostInputEventProfiled")
        ]
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(true, std::memory_order_release)", helper
        )
        self.assertIn("if (g_visiblePauseGesturePassthrough.load", helper)
        self.assertIn("if (released)", helper)
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_release)", helper
        )

        latched = helper[
            helper.index("if (g_visiblePauseGesturePassthrough.load"):
            helper.index("if (!pressed)")
        ]
        self.assertLess(
            latched.index("Forward(input, event, force);"),
            latched.index("g_visiblePauseGesturePassthrough.store(false"),
        )

    def test_clean_pause_retains_gameplay_hud_for_real_resume(self):
        updater = PROFILED[
            PROFILED.index("void UpdateResumeHudSnapshotForPauseInput"):
            PROFILED.index("bool ForwardVisiblePauseGestureIfNeeded")
        ]
        self.assertIn("g_cleanHidden.load", updater)
        self.assertIn("g_pauseGameTarget", updater)
        self.assertIn("g_gameplayHudSnapshot.captured", updater)
        self.assertIn("g_resumeGameplayHudSnapshot = g_gameplayHudSnapshot", updater)
        self.assertIn(
            "g_resumeGameplayHudSnapshotArmed.store(true, std::memory_order_release)", updater
        )

    def test_resume_hud_restore_is_bound_to_pausegame_false(self):
        hook = PROFILED[
            PROFILED.index("void __fastcall HookPauseGameProfiled"):
            PROFILED.index("bool InstallPauseBarrierHook")
        ]
        self.assertIn("&& !pause", hook)
        self.assertIn("g_resumeGameplayHudSnapshotArmed.load", hook)
        self.assertIn("g_originalPauseGame(framework, pause, force, fadeOutInMs);", hook)
        self.assertIn("RestoreHudVisibilitySnapshot", hook)
        self.assertIn('"gameplay-resume-barrier"', hook)

        original_call = hook.index("g_originalPauseGame(framework, pause, force, fadeOutInMs);")
        restore = hook.index("RestoreHudVisibilitySnapshot")
        self.assertLess(original_call, restore)

    def test_latches_and_resume_snapshot_are_reset_at_runtime_boundaries(self):
        start = PROFILED[PROFILED.index("bool Start(HMODULE selfModule)"):]
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_relaxed)", start
        )
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_release)", start
        )
        self.assertIn("g_resumeGameplayHudSnapshot = {};", start)
        self.assertIn(
            "g_resumeGameplayHudSnapshotArmed.store(false, std::memory_order_relaxed)", start
        )
        self.assertIn(
            "g_resumeGameplayHudSnapshotArmed.store(false, std::memory_order_release)", start
        )


if __name__ == "__main__":
    unittest.main()
