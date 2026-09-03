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

    def test_pause_barrier_restores_only_hud_root_before_full_handoff(self):
        helper = PROFILED[
            PROFILED.index("bool RestoreGameplayHudRootAtPauseBarrier"):
            PROFILED.index("void __fastcall HookPauseGameProfiled")
        ]
        self.assertIn("g_gameplayHudSnapshot.captured", helper)
        self.assertIn("kUIElementSetVisibleSlot", helper)
        self.assertIn("kUIElementIsVisibleSlot", helper)
        self.assertIn("g_gameplayHudSnapshot.rootVisible", helper)
        self.assertNotIn("RestoreHudVisibilitySnapshot", helper)
        self.assertNotIn("CaptureHudVisibilitySnapshot", helper)

        hook = PROFILED[
            PROFILED.index("void __fastcall HookPauseGameProfiled"):
            PROFILED.index("bool InstallPauseBarrierHook")
        ]
        original = hook.index("g_originalPauseGame(framework, pause, force, fadeOutInMs);")
        root_restore = hook.index("RestoreGameplayHudRootAtPauseBarrier();")
        barrier = hook.index("g_pauseBarrierObserved.store(true")
        self.assertLess(original, root_restore)
        self.assertLess(root_restore, barrier)

    def test_nearby_pausegame_false_is_logged_for_transition_diagnosis(self):
        hook = PROFILED[
            PROFILED.index("void __fastcall HookPauseGameProfiled"):
            PROFILED.index("bool InstallPauseBarrierHook")
        ]
        self.assertIn("if (!pause)", hook)
        self.assertIn("PauseGame(false) observed", hook)
        self.assertIn("now - pressAt <= 2'000", hook)

    def test_latch_is_reset_at_runtime_boundaries(self):
        start = PROFILED[PROFILED.index("bool Start(HMODULE selfModule)"):]
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_relaxed)", start
        )
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_release)", start
        )


if __name__ == "__main__":
    unittest.main()
