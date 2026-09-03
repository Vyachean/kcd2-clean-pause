import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUBBLES = (ROOT / "native/src/clean_pause_bubbles.cpp").read_text(encoding="utf-8")
HEADER = (ROOT / "native/src/clean_pause_bubbles.h").read_text(encoding="utf-8")


class SharedVisibilityHookContractTests(unittest.TestCase):
    def test_shared_set_visible_hook_filters_only_exact_hud_object(self):
        self.assertIn("using HudRootVisibilityFilterFn", HEADER)
        self.assertIn("SetHudRootVisibilityFilter", HEADER)

        hook = BUBBLES[
            BUBBLES.index("void __fastcall HookMenuSetVisible"):
            BUBBLES.index("bool EnsureSharedVisibilityHook")
        ]
        self.assertIn("element == g_hudElementObject.load", hook)
        self.assertIn("g_hudRootVisibilityFilter.load", hook)
        self.assertIn("if (isHudRoot && hudFilter && hudFilter(visible))", hook)
        self.assertIn("return;", hook)
        self.assertIn("element == g_menuElement", hook)
        self.assertIn("g_originalMenuSetVisible(element, visible)", hook)

    def test_shared_visibility_hook_is_available_before_bubble_rtti_discovery(self):
        ensure = BUBBLES[BUBBLES.index("bool EnsureHooks"):]
        shared = ensure.index("EnsureSharedVisibilityHook(hudElement, menu)")
        discovery = ensure.index("FindBubbleInterface(hudElement)")
        self.assertLess(shared, discovery)

    def test_recreated_hud_cache_identity_is_sampled_before_republication(self):
        ensure = BUBBLES[BUBBLES.index("bool EnsureHooks"):]
        cached = ensure.index("const bool cached")
        shared = ensure.index("EnsureSharedVisibilityHook(hudElement, menu)")
        self.assertLess(cached, shared)


if __name__ == "__main__":
    unittest.main()
