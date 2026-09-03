import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")


class VisiblePauseGestureContractTests(unittest.TestCase):
    def test_visible_menu_is_checked_before_clean_pause_preparation(self):
        helper = RUNTIME[
            RUNTIME.index("bool ForwardVisiblePauseGestureIfNeeded"):
            RUNTIME.index("void __fastcall HookPostInputEventProfiled")
        ]
        self.assertIn("ReadVerifiedMenuVisible", helper)
        self.assertIn("EnsureMenuRenderHook", helper)
        self.assertIn("g_visiblePauseGesturePassthrough", helper)
        self.assertIn("Forward(input, event, force);", helper)
        self.assertNotIn("CaptureHudVisibilitySnapshot", helper)
        self.assertNotIn("ResetHudSnapshots", helper)

        wrapper = RUNTIME[
            RUNTIME.index("void __fastcall HookPostInputEventProfiled"):
            RUNTIME.index("bool InstallInputHook")
        ]
        preflight = wrapper.index("ForwardVisiblePauseGestureIfNeeded")
        deferred_barrier = wrapper.index("ShouldTryDeferredPauseBarrier")
        shared_core = wrapper.index("HookPostInputEventCore")
        self.assertLess(preflight, deferred_barrier)
        self.assertLess(preflight, shared_core)

    def test_visible_menu_passthrough_latches_until_physical_release(self):
        helper = RUNTIME[
            RUNTIME.index("bool ForwardVisiblePauseGestureIfNeeded"):
            RUNTIME.index("void __fastcall HookPostInputEventProfiled")
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

    def test_steam_root_visibility_filter_pins_only_owned_pause_presentation(self):
        helper = RUNTIME[
            RUNTIME.index("bool ShouldSuppressProfileHudRootVisibility"):
            RUNTIME.index("bool RestoreGameplayHudRootAtPauseBarrier")
        ]
        self.assertIn("Storefront::Steam", helper)
        self.assertIn("g_hudMaskPinSuspended.load", helper)
        self.assertIn("g_gameplayHudSnapshot.captured", helper)
        self.assertIn("g_pauseTransitionActive.load", helper)
        self.assertIn("g_cleanHidden.load", helper)
        self.assertIn("visible == g_gameplayHudSnapshot.rootVisible", helper)
        self.assertIn("return true;", helper)

        install = RUNTIME[
            RUNTIME.index("bool InstallInputHook"):
            RUNTIME.index("bool PollRuntimeEnvironment")
        ]
        self.assertIn("bubbles::SetHudRootVisibilityFilter", install)
        self.assertIn("&ShouldSuppressProfileHudRootVisibility", install)

        stop = RUNTIME[RUNTIME.index("void Stop()"):]
        self.assertIn("bubbles::SetHudRootVisibilityFilter(nullptr)", stop)

    def test_pause_barrier_defensively_restores_only_hud_root(self):
        helper = RUNTIME[
            RUNTIME.index("bool RestoreGameplayHudRootAtPauseBarrier"):
            RUNTIME.index("bool ShouldPrehideEntryRender")
        ]
        self.assertIn("g_gameplayHudSnapshot.captured", helper)
        self.assertIn("kUIElementSetVisibleSlot", helper)
        self.assertIn("kUIElementIsVisibleSlot", helper)
        self.assertIn("g_gameplayHudSnapshot.rootVisible", helper)
        self.assertNotIn("RestoreHudVisibilitySnapshot", helper)
        self.assertNotIn("CaptureHudVisibilitySnapshot", helper)

        hook = RUNTIME[
            RUNTIME.index("void __fastcall HookPauseGameProfiled"):
            RUNTIME.index("bool InstallPauseBarrierHook")
        ]
        original = hook.index("g_originalPauseGame(framework, pause, force, fadeOutInMs);")
        root_restore = hook.index("RestoreGameplayHudRootAtPauseBarrier();")
        barrier = hook.index("g_pauseBarrierObserved.store(true")
        self.assertLess(original, root_restore)
        self.assertLess(root_restore, barrier)

    def test_steam_entry_render_prehide_covers_pause_handoff(self):
        hook = RUNTIME[
            RUNTIME.index("void __fastcall HookPauseGameProfiled"):
            RUNTIME.index("bool InstallPauseBarrierHook")
        ]
        arm = hook.index("g_entryRenderPrehide.store(true")
        hide = hook.index("g_cleanHidden.store(true")
        original = hook.index("g_originalPauseGame(framework, pause, force, fadeOutInMs);")
        self.assertLess(arm, hide)
        self.assertLess(hide, original)
        self.assertIn("ShouldPrehideEntryRender", hook)
        self.assertIn("RollBackEntryRenderPrehide", hook)

        wrapper = RUNTIME[
            RUNTIME.index("void __fastcall HookPostInputEventProfiled"):
            RUNTIME.index("bool InstallInputHook")
        ]
        shared_core = wrapper.index("HookPostInputEventCore")
        settle = wrapper.index("g_entryRenderPrehide.exchange(false")
        self.assertLess(shared_core, settle)
        self.assertIn("g_cleanHiddenSinceMs.load", wrapper)
        self.assertIn("g_cleanHidden.store(false", wrapper)
        self.assertIn("entry render prehide committed", wrapper)

    def test_latch_is_reset_at_runtime_boundaries(self):
        start = RUNTIME[RUNTIME.index("bool Start(HMODULE selfModule)"):]
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_relaxed)", start
        )
        self.assertIn(
            "g_visiblePauseGesturePassthrough.store(false, std::memory_order_release)", start
        )
        self.assertIn(
            "g_entryRenderPrehide.store(false, std::memory_order_relaxed)", start
        )
        self.assertIn(
            "g_entryRenderPrehide.store(false, std::memory_order_release)", start
        )


if __name__ == "__main__":
    unittest.main()
