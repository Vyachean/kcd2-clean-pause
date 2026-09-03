import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
ABI = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")
MASK = (ROOT / "native/src/clean_pause_hud_mask.cpp").read_text(encoding="utf-8")
BUBBLES = (ROOT / "native/src/clean_pause_bubbles.cpp").read_text(encoding="utf-8")


class PauseBarrierContractTests(unittest.TestCase):
    def test_verified_framework_surface_is_declared(self):
        for needle in (
            "kGameGetFrameworkSlot = 16",
            "kGameFrameworkPauseGameSlot = 13",
            "kGameFrameworkGetSystemSlot = 19",
            "using PauseGameFn =",
        ):
            self.assertIn(needle, ABI)

    def test_framework_identity_is_not_shape_only(self):
        xbox = NATIVE[
            NATIVE.index("bool LegacyResolveGameFramework_Xbox156Only"):
            NATIVE.index("} // namespace\n\n} // namespace clean_pause")
        ]
        self.assertIn("frameworkSystem == environment.system", xbox)
        self.assertIn("kGameGetFrameworkSlot", xbox)
        self.assertIn("kGameFrameworkGetSystemSlot", xbox)

        profile_singleton = NATIVE[
            NATIVE.index("bool ResolveProfileFrameworkSingleton"):
            NATIVE.index("bool ResolveGameFramework")
        ]
        self.assertIn("FrameworkLocatorStrategy::ExactSingletonRva", profile_singleton)
        self.assertIn("expectedFrameworkStorageRva", profile_singleton)
        self.assertIn("expectedFrameworkVtableRva", profile_singleton)
        self.assertIn("frameworkSystem != environment.system", profile_singleton)
        self.assertIn("kGameFrameworkGetSystemSlot", profile_singleton)
        self.assertNotIn("Storefront::Steam", profile_singleton)
        self.assertNotIn("kGameGetFrameworkSlot", profile_singleton)

    def test_pause_hook_keeps_exact_vanilla_ownership_and_scopes_pinning_to_pause_call(self):
        hook = NATIVE[NATIVE.index("void __fastcall HookPauseGame"):NATIVE.index("bool InstallPauseBarrierHook")]
        self.assertIn("framework == g_gameFramework", hook)
        self.assertIn("g_pendingPauseAttempt.load", hook)
        self.assertIn("if (!g_originalPauseGame)", hook)
        self.assertIn("g_pauseTransitionActive.store(true", hook)
        self.assertIn("g_originalPauseGame(framework, pause, force, fadeOutInMs);", hook)
        self.assertNotIn("effectiveFadeOutInMs", hook)
        self.assertLess(hook.index("g_pauseTransitionActive.store(true"), hook.index("g_originalPauseGame("))
        self.assertLess(hook.index("g_originalPauseGame("), hook.index("g_pauseBarrierObserved.store(true"))
        self.assertEqual(NATIVE.count("g_originalPauseGame("), 1)

    def test_pending_input_correlation_does_not_pin_or_freeze_hud(self):
        freeze = NATIVE[NATIVE.index("bool ShouldFreezeHudFunction"):NATIVE.index("bool __fastcall HookHudCallFunction")]
        pin = NATIVE[NATIVE.index("bool ShouldPinGameplayHudPresentation"):NATIVE.index("bool CaptureVanillaHudFromInternalMask")]
        self.assertIn("g_pauseTransitionActive.load", freeze)
        self.assertIn("g_pauseTransitionActive.load", pin)
        self.assertNotIn("g_pendingPauseAttempt.load", freeze)
        self.assertNotIn("g_pendingPauseAttempt.load", pin)

    def test_release_consumes_pause_barrier_and_logs_transition_timing(self):
        post = NATIVE[NATIVE.index("void __fastcall HookPostInputEvent"):NATIVE.index("bool ResolveGameFramework")]
        self.assertIn("pause physical press:", post)
        self.assertIn("pause press preparation complete; setupMs=%llu", post)
        self.assertIn("pause physical release: key=%u sincePressMs=%llu", post)
        self.assertIn("pause release vanilla dispatch returned; dispatchMs=%llu barrier=%s", post)
        self.assertIn("vanilla PauseGame barrier after Escape/Start release", post)

    def test_barrier_consumed_after_outer_press_forward(self):
        post = NATIVE[NATIVE.index("void __fastcall HookPostInputEvent"):NATIVE.index("bool ResolveGameFramework")]
        barrier = post.index("g_pauseBarrierObserved.exchange(false")
        self.assertGreater(post.rfind("Forward(input, event, force);", 0, barrier), -1)
        self.assertIn(
            'TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)',
            post,
        )
        self.assertIn("Compatibility fallback", post)

    def test_cached_hud_discovery_is_scoped_to_hud_identity(self):
        self.assertIn("g_hudElementObject", MASK)
        self.assertIn("LoadCachedMaskObjects", MASK)
        self.assertIn("g_hudElementObject.load(std::memory_order_acquire) != hudElement", MASK)
        self.assertIn("g_hudElementObject", BUBBLES)
        self.assertIn("g_hudElementObject.load(std::memory_order_acquire) == hudElement", BUBBLES)
        self.assertIn("hud == g_hudUpdateElement", NATIVE)


if __name__ == "__main__":
    unittest.main()
