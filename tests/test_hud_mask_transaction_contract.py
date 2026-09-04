import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
MASK = (ROOT / "native/src/clean_pause_hud_mask.cpp").read_text(encoding="utf-8")
MASK_H = (ROOT / "native/src/clean_pause_hud_mask.h").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class HudMaskTransactionContractTests(unittest.TestCase):
    def test_runtime_discovers_concrete_hud_mask_without_fixed_rva(self):
        self.assertIn('.?AVC_UIHudMask@guimodule@wh@@', MASK)
        self.assertIn('kMaskListenerOffset = 0x10', MASK)
        self.assertIn('kMaskVisibilityInterfaceOffset = 0x58', MASK)
        self.assertIn('kMaskSourceMonitorOffset = 0x60', MASK)
        self.assertIn('kHudListenersOffset = 0x1D0', MASK)
        self.assertNotIn('0x548BFA8', MASK)
        self.assertNotIn('0x180555978', MASK)

    def test_module_message_hook_filters_to_verified_refresh_message(self):
        self.assertIn('kModuleMessageIdOffset = 0x08', MASK)
        self.assertIn('kHudRefreshModuleMessageId = 52', MASK)
        hook = MASK[MASK.index('void __fastcall HookOnModuleMessage'):MASK.index('} // namespace\n\nbool EnsureHooks')]
        self.assertLess(hook.index('IsHudRefreshMessage(message)'), hook.index('g_originalOnModuleMessage'))
        self.assertIn('if (refresh)\n        NotifyAfterMutation();', hook)

    def test_global_method_hooks_filter_to_the_discovered_hud_mask_instance(self):
        self.assertIn('std::atomic<void*> g_maskObject{nullptr};', MASK)
        self.assertIn('std::atomic<void*> g_sourceMonitorObject{nullptr};', MASK)
        source = MASK[MASK.index('void __fastcall HookSourceEvent'):MASK.index('void __fastcall HookOnModuleMessage')]
        self.assertIn('sourceMonitor == g_sourceMonitorObject.load', source)
        module = MASK[MASK.index('void __fastcall HookOnModuleMessage'):MASK.index('} // namespace\n\nbool EnsureHooks')]
        self.assertIn('mask == g_maskObject.load', module)
        ensure = MASK[MASK.index('bool EnsureHooks'):MASK.index('bool ReadCurrentVisibility')]
        # Cached reuse may update the observer before the initial-publication block.
        # The first installation must still publish both concrete identities before
        # the final observer publication that makes new detours active.
        self.assertLess(ensure.index('g_maskObject.store'), ensure.rindex('g_observer.store'))
        self.assertLess(ensure.index('g_sourceMonitorObject.store'), ensure.rindex('g_observer.store'))

    def test_transaction_fails_open_when_authoritative_state_is_unavailable(self):
        callback = NATIVE[NATIVE.index('void FailOpenHudMaskTransaction'):NATIVE.index('void FailOpenHudMaintenance')]
        reconcile = callback[callback.index('void ReconcileHudMaskMutation'):]
        self.assertIn('if (!CaptureVanillaHudFromInternalMask(vanillaState))', reconcile)
        self.assertIn('fallback.captured ? &fallback : nullptr', reconcile)
        self.assertIn('FailOpenHudMaskTransaction(&vanillaState', reconcile)
        self.assertLess(reconcile.index('CaptureVanillaHudFromInternalMask'), reconcile.index('RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot'))

    def test_transactional_entry_requires_fresh_internal_state(self):
        entry = NATIVE[NATIVE.index('bool TryEnterCleanPause'):NATIVE.index('void HandleHiddenInput')]
        transactional = entry[entry.index('if (transactional)'):entry.index('if (!transactional')]
        self.assertIn('if (!CaptureVanillaHudFromInternalMask(currentVanilla))', transactional)
        self.assertIn('return false;', transactional)
        self.assertIn('g_vanillaPauseHudSnapshot = currentVanilla;', transactional)

    def test_terminal_entry_failure_does_not_rearm_pending_attempt(self):
        post = NATIVE[NATIVE.index('void __fastcall HookPostInputEvent'):NATIVE.index('bool InstallInputHook')]
        self.assertEqual(post.count('&& g_gameplayHudSnapshot.captured)\n            ArmPendingPauseAttempt();'), 2)

    def test_vanilla_mutation_runs_before_visual_reconciliation(self):
        source = MASK[MASK.index('void __fastcall HookSourceEvent'):MASK.index('void __fastcall HookOnModuleMessage')]
        self.assertLess(source.index('g_originalSourceEvent'), source.index('NotifyAfterMutation'))
        module = MASK[MASK.index('void __fastcall HookOnModuleMessage'):MASK.index('} // namespace\n\nbool EnsureHooks')]
        self.assertLess(module.index('g_originalOnModuleMessage'), module.index('NotifyAfterMutation'))

    def test_live_vanilla_state_comes_from_internal_mask_interface(self):
        self.assertIn('kMaskIsElementVisibleSlot = 1', MASK)
        self.assertIn('ReadCurrentVisibility', MASK_H)
        read = MASK[MASK.index('bool ReadCurrentVisibility'):]
        self.assertIn('kMaskVisibilityInterfaceOffset', read)
        self.assertIn('VFunc<IsElementVisibleFn>', read)
        self.assertIn('count != kHudElementCount', read)

    def test_snapshot_preserves_root_hud_visibility_exactly(self):
        snapshot = NATIVE[NATIVE.index('struct HudVisibilitySnapshot'):NATIVE.index('HudVisibilitySnapshot g_gameplayHudSnapshot')]
        self.assertIn('bool rootVisible{};', snapshot)
        capture = NATIVE[NATIVE.index('bool CaptureHudVisibilitySnapshot'):NATIVE.index('bool RestoreHudVisibilitySnapshot')]
        restore = NATIVE[NATIVE.index('bool RestoreHudVisibilitySnapshot'):NATIVE.index('bool ShouldPinGameplayHudPresentation')]
        internal = NATIVE[NATIVE.index('bool CaptureVanillaHudFromInternalMask'):NATIVE.index('bool RestoreVanillaHudPresentation')]
        self.assertIn('next.rootVisible = rootVisible;', capture)
        self.assertIn('target.rootVisible = rootVisible;', internal)
        self.assertIn('if (currentRootVisible && !snapshot.rootVisible)', restore)
        self.assertIn('if (!currentRootVisible && snapshot.rootVisible)', restore)

    def test_transaction_read_failure_uses_prior_complete_internal_fallback(self):
        reconcile = NATIVE[NATIVE.index('void ReconcileHudMaskMutation()'):NATIVE.index('void FailOpenHudMaintenance')]
        self.assertIn('const HudVisibilitySnapshot fallback = g_vanillaPauseHudSnapshot;', reconcile)
        self.assertIn('fallback.captured ? &fallback : nullptr', reconcile)

    def test_runtime_logs_whgame_fingerprint_for_future_abi_gating(self):
        bootstrap = NATIVE[NATIVE.index('DWORD WINAPI BootstrapThread'):]
        self.assertIn('kcd2::runtime::ReadBuildIdentity(whGame, identity)', bootstrap)
        self.assertIn('TimeDateStamp=0x%08lx SizeOfImage=0x%08lx CheckSum=0x%08lx', bootstrap)
        self.assertIn('identity.fingerprint.timestamp', bootstrap)
        self.assertIn('identity.fingerprint.imageSize', bootstrap)
        self.assertIn('identity.fingerprint.checksum', bootstrap)
        self.assertLess(
            bootstrap.index('kcd2::runtime::ReadBuildIdentity(whGame, identity)'),
            bootstrap.index('kcd2::runtime::MatchSupportedBuild(identity)'),
        )

    def test_transaction_never_whole_snapshots_partial_flash_state(self):
        callback = NATIVE[NATIVE.index('void ReconcileHudMaskMutation()'):NATIVE.index('void FailOpenHudMaintenance')]
        self.assertNotIn('CaptureHudVisibilitySnapshot', callback)
        self.assertIn('CaptureVanillaHudFromInternalMask', callback)
        self.assertIn('g_vanillaPauseHudSnapshot = vanillaState;', callback)
        self.assertIn('RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot', callback)
        self.assertLess(callback.index('GetCurrentThreadId()'), callback.index('ShouldPinGameplayHudPresentation()'))

    def test_pending_transaction_expires_without_requiring_another_input(self):
        update = NATIVE[NATIVE.index('void __fastcall HookHudUpdate'):NATIVE.index('bool EnsureHudUpdateHook')]
        self.assertIn('g_pendingPauseAttempt.load(std::memory_order_acquire)', update)
        self.assertIn('now > deadline', update)
        self.assertIn('RestoreVanillaHudPresentation("vanilla-pending-timeout-update")', update)
        self.assertLess(update.index('g_hudMaskPinSuspended.store(true'), update.index('RestoreVanillaHudPresentation("vanilla-pending-timeout-update")'))
        self.assertLess(update.index('RestoreVanillaHudPresentation("vanilla-pending-timeout-update")'), update.index('ResetHudSnapshots()'))

    def test_transaction_mode_does_not_require_fallback_vanilla_snapshot(self):
        entry = NATIVE[NATIVE.index('bool TryEnterCleanPause'):NATIVE.index('void HandleHiddenInput')]
        self.assertIn('const bool transactional', entry)
        self.assertIn('if (!transactional', entry)
        self.assertIn('CaptureHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause")', entry)

    def test_clean_pause_exit_suspends_all_pinning_before_live_restore(self):
        hidden = NATIVE[NATIVE.index('void HandleHiddenInput'):NATIVE.index('void __fastcall HookPostInputEvent')]
        start = hidden[hidden.index('if (IsPauseKey(key))'):hidden.index('if (key == KeyId::XiB)')]
        self.assertLess(start.index('g_hudMaskPinSuspended.store(true'), start.index('RestoreVanillaHudPresentation'))
        self.assertLess(start.index('RestoreVanillaHudPresentation'), start.index('g_cleanHidden.store(false'))
        self.assertLess(start.index('g_cleanHidden.store(false'), start.index('g_hudMaskPinSuspended.store(false'))

        b_path = hidden[hidden.index('if (key == KeyId::XiB)'):]
        self.assertLess(b_path.index('g_hudMaskPinSuspended.store(true'), b_path.index('RestoreVanillaHudPresentation'))
        self.assertLess(b_path.index('RestoreVanillaHudPresentation'), b_path.index('g_cleanHidden.store(false'))
        self.assertLess(b_path.index('g_cleanHidden.store(false'), b_path.index('g_hudMaskPinSuspended.store(false'))

    def test_periodic_fallback_respects_exit_suspension(self):
        update = NATIVE[NATIVE.index('void __fastcall HookHudUpdate'):NATIVE.index('bool EnsureHudUpdateHook')]
        self.assertIn('g_hudMaskPinSuspended.load(std::memory_order_acquire)', update)

    def test_pending_expiry_restores_live_vanilla_state_before_reset(self):
        pending = NATIVE[NATIVE.index('bool PendingAttemptAlive'):NATIVE.index('bool TryEnterCleanPause')]
        self.assertLess(pending.index('g_hudMaskPinSuspended.store(true'), pending.index('RestoreVanillaHudPresentation'))
        self.assertLess(pending.index('RestoreVanillaHudPresentation'), pending.index('ResetHudSnapshots'))

    def test_no_waiting_mechanism_is_added_to_transaction(self):
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
