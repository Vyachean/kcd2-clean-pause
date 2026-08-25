import unittest
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
