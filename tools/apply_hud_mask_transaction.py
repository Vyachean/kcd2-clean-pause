from pathlib import Path

path = Path("native/src/clean_pause_native.cpp")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match, found {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)


replace_once(
    '#include "clean_pause_bubbles.h"\n#include "kcd2_abi.h"',
    '#include "clean_pause_bubbles.h"\n#include "clean_pause_hud_mask.h"\n#include "kcd2_abi.h"',
)

replace_once(
    '    return true;\n}\n\nvoid FailOpenHudMaintenance(const char* reason)',
    '''    return true;\n}\n\nbool ShouldPinGameplayHudPresentation()\n{\n    if (!g_gameplayHudSnapshot.captured)\n        return false;\n    if (g_cleanHidden.load(std::memory_order_acquire))\n        return true;\n    if (!g_pendingPauseAttempt.load(std::memory_order_acquire))\n        return false;\n\n    const ULONGLONG deadline = g_pendingDeadlineMs.load(std::memory_order_acquire);\n    return deadline != 0 && GetTickCount64() <= deadline;\n}\n\nvoid ReconcileHudMaskMutation()\n{\n    // C_UIHudMask has already updated its internal source-derived state here, but\n    // rendering has not resumed yet. Capture that vanilla pause state, then put the\n    // pre-pause presentation back in the same call stack so no hidden HUD frame can\n    // reach the renderer. Internal vanilla ownership is intentionally untouched.\n    if (!ShouldPinGameplayHudPresentation())\n        return;\n    if (!OnValidatedMainThread("HUD mask transaction"))\n        return;\n\n    HudVisibilitySnapshot vanillaState{};\n    if (!CaptureHudVisibilitySnapshot(vanillaState, "vanilla-mask-transaction")) {\n        Log("C_UIHudMask transaction could not capture vanilla HUD state; periodic fallback remains active");\n        return;\n    }\n    g_vanillaPauseHudSnapshot = vanillaState;\n\n    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-mask-transaction"))\n        Log("C_UIHudMask transaction could not restore gameplay HUD before render; periodic fallback remains active");\n}\n\nvoid FailOpenHudMaintenance(const char* reason)''',
)

replace_once(
    '''    // Overhead NPC subtitles are managed by C_UIHudBubbles below the root "Bubbles"\n    // movieclip. Install their optional lifecycle freeze before vanilla sees Start.''',
    '''    // C_UIHudMask is the source-derived owner of the 28 child visibility flags.\n    // Observe its mutations before vanilla sees Start so a pause-source update can be\n    // visually rolled back in the same call stack, before the next render.\n    if (!hud_mask::EnsureHooks(hud, &ReconcileHudMaskMutation))\n        Log("C_UIHudMask transaction hook unavailable; using snapshot restore fallback");\n\n    // Overhead NPC subtitles are managed by C_UIHudBubbles below the root "Bubbles"\n    // movieclip. Install their optional lifecycle freeze before vanilla sees Start.''',
)

replace_once(
    '''    if (!g_gameplayHudSnapshot.captured\n        || !CaptureHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause")) {''',
    '''    if (!g_gameplayHudSnapshot.captured\n        || (!g_vanillaPauseHudSnapshot.captured\n            && !CaptureHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause"))) {''',
)

path.write_text(text, encoding="utf-8")

Path("tests/test_hud_mask_transaction_contract.py").write_text(r'''import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
MASK = (ROOT / "native/src/clean_pause_hud_mask.cpp").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class HudMaskTransactionContractTests(unittest.TestCase):
    def test_runtime_discovers_concrete_hud_mask_without_fixed_rva(self):
        self.assertIn('.?AVC_UIHudMask@guimodule@wh@@', MASK)
        self.assertIn('kMaskListenerOffset = 0x10', MASK)
        self.assertIn('kMaskSourceMonitorOffset = 0x60', MASK)
        self.assertIn('kHudListenersOffset = 0x1D0', MASK)
        self.assertNotIn('0x548BFA8', MASK)
        self.assertNotIn('0x180555978', MASK)

    def test_vanilla_mutation_runs_before_visual_reconciliation(self):
        source = MASK[MASK.index('void __fastcall HookSourceEvent'):MASK.index('void __fastcall HookOnModuleMessage')]
        self.assertLess(source.index('g_originalSourceEvent'), source.index('NotifyAfterMutation'))
        module = MASK[MASK.index('void __fastcall HookOnModuleMessage'):MASK.index('} // namespace\n\nbool EnsureHooks')]
        self.assertLess(module.index('g_originalOnModuleMessage'), module.index('NotifyAfterMutation'))

    def test_transaction_captures_vanilla_then_restores_gameplay_before_return(self):
        callback = NATIVE[NATIVE.index('void ReconcileHudMaskMutation()'):NATIVE.index('void FailOpenHudMaintenance')]
        self.assertIn('ShouldPinGameplayHudPresentation()', callback)
        self.assertIn('OnValidatedMainThread("HUD mask transaction")', callback)
        self.assertLess(callback.index('CaptureHudVisibilitySnapshot'), callback.index('RestoreHudVisibilitySnapshot'))
        self.assertIn('g_vanillaPauseHudSnapshot = vanillaState;', callback)
        self.assertIn('g_gameplayHudSnapshot', callback)

    def test_entry_reuses_transactionally_captured_vanilla_state(self):
        entry = NATIVE[NATIVE.index('bool TryEnterCleanPause'):NATIVE.index('void HandleHiddenInput')]
        self.assertIn('!g_vanillaPauseHudSnapshot.captured', entry)
        self.assertIn('CaptureHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause")', entry)

    def test_no_waiting_mechanism_is_added(self):
        callback = NATIVE[NATIVE.index('void ReconcileHudMaskMutation()'):NATIVE.index('void FailOpenHudMaintenance')]
        self.assertNotIn('Sleep(', callback)
        self.assertNotIn('while (', callback)
        self.assertNotIn('CreateThread', callback)

    def test_mask_hook_is_part_of_both_native_editions(self):
        self.assertIn('src/clean_pause_hud_mask.cpp', CMAKE)
        self.assertIn('src/clean_pause_hud_mask.h', CMAKE)
        self.assertIn('hud_mask::EnsureHooks(hud, &ReconcileHudMaskMutation)', NATIVE)


if __name__ == '__main__':
    unittest.main()
''', encoding="utf-8")
