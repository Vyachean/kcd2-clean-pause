from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BUBBLES = (ROOT / "native/src/clean_pause_bubbles.cpp").read_text(encoding="utf-8")
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class BubbleContractTests(unittest.TestCase):
    def test_controller_is_shared_by_both_native_editions(self):
        self.assertIn("src/clean_pause_bubbles.cpp", CMAKE)
        runtime_start = CMAKE.index("set(CLEAN_PAUSE_RUNTIME_SOURCES")
        runtime_end = CMAKE.index(")", runtime_start)
        runtime = CMAKE[runtime_start:runtime_end]
        self.assertIn("src/clean_pause_bubbles.cpp", runtime)
        self.assertIn("src/clean_pause_bubbles.h", runtime)

    def test_discovers_hud_bubbles_from_listener_rtti_without_fixed_rva(self):
        self.assertIn("kHudListenersOffset = 0x1D0", BUBBLES)
        self.assertIn("kBubbleListenerOffset = 0x10", BUBBLES)
        self.assertIn("kBubbleInterfaceOffset = 0x58", BUBBLES)
        self.assertIn(".?AVC_UIHudBubbles@guimodule@wh@@", BUBBLES)
        self.assertIn("CompleteObjectLocator64", BUBBLES)
        self.assertIn("locator->selfRva", BUBBLES)
        self.assertIn('GetModuleHandleW(L"WHGame.dll")', BUBBLES)
        for forbidden in (
            "0x549D388",
            "0x3C297C8",
            "0x1805E0520",
            "0x1814BE954",
            "REL::ID",
        ):
            self.assertNotIn(forbidden, BUBBLES)

    def test_freezes_only_update_and_release_while_vanilla_menu_is_open(self):
        self.assertIn("kBubbleUpdateSlot = 1", BUBBLES)
        self.assertIn("kBubbleReleaseSlot = 3", BUBBLES)
        update = BUBBLES[BUBBLES.index("void __fastcall HookBubbleUpdate"):]
        update = update[: update.index("void __fastcall HookBubbleRelease")]
        release = BUBBLES[BUBBLES.index("void __fastcall HookBubbleRelease"):]
        release = release[: release.index("void __fastcall HookMenuSetVisible")]
        for block in (update, release):
            self.assertIn("g_pauseMenuVisible.load", block)
            self.assertIn("return;", block)
        self.assertNotIn("HookBubbleSetText", BUBBLES)
        self.assertNotIn("HookBubbleSetAnchor", BUBBLES)

    def test_global_bubble_method_hooks_are_scoped_to_discovered_instance(self):
        self.assertIn('std::atomic<void*> g_bubbleInterfaceObject{nullptr};', BUBBLES)
        update = BUBBLES[BUBBLES.index('void __fastcall HookBubbleUpdate'):BUBBLES.index('void __fastcall HookBubbleRelease')]
        release = BUBBLES[BUBBLES.index('void __fastcall HookBubbleRelease'):BUBBLES.index('void __fastcall HookMenuSetVisible')]
        self.assertIn('bubbles == g_bubbleInterfaceObject.load', update)
        self.assertIn('bubbles == g_bubbleInterfaceObject.load', release)
        ensure = BUBBLES[BUBBLES.index('bool EnsureHooks'):]
        self.assertLess(
            ensure.index('EnsureSharedVisibilityHook(hudElement, menu)'),
            ensure.index('g_bubbleInterfaceObject.store'),
        )

    def test_menu_freeze_arms_before_vanilla_show_and_releases_after_hide(self):
        hook = BUBBLES[BUBBLES.index("void __fastcall HookMenuSetVisible"):]
        hook = hook[: hook.index("bool EnsureSharedVisibilityHook")]
        arm = 'g_pauseMenuVisible.store(true, std::memory_order_release);'
        forward = "g_originalMenuSetVisible(element, visible);"
        release = 'g_pauseMenuVisible.store(false, std::memory_order_release);'
        self.assertLess(hook.index(arm), hook.index(forward))
        self.assertLess(hook.index(forward), hook.index(release))

    def test_hook_installation_is_optional_and_happens_before_pause_forwarding(self):
        ensure = NATIVE[NATIVE.index("bool EnsureHudUpdateHook()"):]
        ensure = ensure[: ensure.index("void __fastcall HookMenuRender")]
        self.assertIn("bubbles::EnsureHooks(hud, g_flashUI);", ensure)

        post_input = NATIVE[NATIVE.index("void __fastcall HookPostInputEvent"):]
        pause = post_input[post_input.index("if (pressed) {"):]
        pause = pause[: pause.index("if (released && PendingAttemptAlive())")]
        self.assertLess(pause.index("EnsureHudUpdateHook()"), pause.index("Forward(input, event, force);"))
        # Bubble discovery is explicitly best-effort: it is not part of the fail-open
        # condition that decides whether Clean Pause itself remains available.
        self.assertNotIn("!bubbles::EnsureHooks", NATIVE)


if __name__ == "__main__":
    unittest.main()
