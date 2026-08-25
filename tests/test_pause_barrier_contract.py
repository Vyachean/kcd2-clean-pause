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
        resolver = NATIVE[NATIVE.index("bool ResolveGameFramework"):NATIVE.index("void __fastcall HookPauseGame")]
        self.assertIn("frameworkSystem == environment.system", resolver)
        self.assertIn("kGameGetFrameworkSlot", resolver)
        self.assertIn("kGameFrameworkGetSystemSlot", resolver)

    def test_pause_hook_is_observer_only_and_after_original(self):
        hook = NATIVE[NATIVE.index("void __fastcall HookPauseGame"):NATIVE.index("bool InstallPauseBarrierHook")]
        self.assertIn("framework == g_gameFramework", hook)
        self.assertIn("g_pendingPauseAttempt.load", hook)
        self.assertLess(hook.index("g_originalPauseGame("), hook.index("g_pauseBarrierObserved.store(true"))
        self.assertEqual(NATIVE.count("g_originalPauseGame("), 1)

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
