from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MASK_PATH = ROOT / "native/src/clean_pause_hud_mask.cpp"
NATIVE_PATH = ROOT / "native/src/clean_pause_native.cpp"
TEST_PATH = ROOT / "tests/test_hud_mask_transaction_contract.py"
VALIDATOR_PATH = ROOT / "tools/validate_native_contract.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


mask = MASK_PATH.read_text(encoding="utf-8")
mask = replace_once(
    mask,
    '''OnModuleMessageFn g_originalOnModuleMessage{};
void* g_onModuleMessageTarget{};
''',
    '''OnModuleMessageFn g_originalOnModuleMessage{};
void* g_onModuleMessageTarget{};
std::atomic<void*> g_maskObject{nullptr};
std::atomic<void*> g_sourceMonitorObject{nullptr};
''',
    "target object state",
)
mask = replace_once(
    mask,
    '''void __fastcall HookSourceEvent(void* sourceMonitor, void* source, bool active)
{
    if (g_originalSourceEvent)
        g_originalSourceEvent(sourceMonitor, source, active);
    NotifyAfterMutation();
}
''',
    '''void __fastcall HookSourceEvent(void* sourceMonitor, void* source, bool active)
{
    if (g_originalSourceEvent)
        g_originalSourceEvent(sourceMonitor, source, active);

    // MinHook patches the shared method body, not one C_UIHudMask instance. Only the
    // source-monitor object discovered from the current hud@0 may drive reconciliation.
    if (sourceMonitor == g_sourceMonitorObject.load(std::memory_order_acquire))
        NotifyAfterMutation();
}
''',
    "source instance filter",
)
mask = replace_once(
    mask,
    '''void __fastcall HookOnModuleMessage(void* mask, void* message)
{
    // All GUI elements receive the general module-message broadcast. C_UIHudMask
    // mutates visibility only for message id 52; read that id before vanilla runs so
    // the message object does not need to outlive the original call.
    const bool refresh = IsHudRefreshMessage(message);
    if (g_originalOnModuleMessage)
        g_originalOnModuleMessage(mask, message);
    if (refresh)
        NotifyAfterMutation();
}
''',
    '''void __fastcall HookOnModuleMessage(void* mask, void* message)
{
    // MinHook patches the class method globally. Ignore other C_UIHudMask instances,
    // and for the target instance react only to verified HUD-refresh message id 52.
    // Read the id before vanilla runs so the message does not need to outlive the call.
    const bool targetMask = mask == g_maskObject.load(std::memory_order_acquire);
    const bool refresh = targetMask && IsHudRefreshMessage(message);
    if (g_originalOnModuleMessage)
        g_originalOnModuleMessage(mask, message);
    if (refresh)
        NotifyAfterMutation();
}
''',
    "module instance filter",
)
mask = replace_once(
    mask,
    '''    g_observer.store(observer, std::memory_order_release);
    return true;
}
''',
    '''    // Publish the concrete instance identities before the observer. The detours
    // remain inert for unrelated instances and during partial installation.
    g_maskObject.store(mask, std::memory_order_release);
    g_sourceMonitorObject.store(sourceMonitor, std::memory_order_release);
    g_observer.store(observer, std::memory_order_release);
    return true;
}
''',
    "instance publication ordering",
)
MASK_PATH.write_text(mask, encoding="utf-8")

native = NATIVE_PATH.read_text(encoding="utf-8")
old_reconcile = '''void ReconcileHudMaskMutation()
{
    // The mask callback can be entered through generic engine dispatch. Validate the
    // thread before touching the non-atomic snapshot structs or mutating Flash.
    if (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId) {
        if (!g_hudMaskThreadMismatchLogged.exchange(true, std::memory_order_acq_rel))
            Log("C_UIHudMask mutation observed off validated main thread; transactional HUD pin skipped");
        return;
    }
    if (!ShouldPinGameplayHudPresentation())
        return;

    // Vanilla has already updated its internal C_UIHudMask state. Snapshot that
    // authoritative 28-element state (not the partially-mutated Flash presentation)
    // so a later discovery failure can still relinquish Clean Pause safely.
    HudVisibilitySnapshot vanillaState{};
    if (CaptureVanillaHudFromInternalMask(vanillaState))
        g_vanillaPauseHudSnapshot = vanillaState;

    // Only presentation is rolled back. KCD2 keeps owning the internal pause state.
    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-mask-transaction"))
        Log("C_UIHudMask transaction could not restore gameplay HUD before render; periodic fallback remains active");
}

'''
new_reconcile = '''void FailOpenHudMaskTransaction(
    const HudVisibilitySnapshot* vanillaState,
    const char* reason)
{
    // The original C_UIHudMask mutation has already run. If gameplay replay has not
    // started, current Flash is already vanilla; otherwise use the authoritative
    // internal snapshot captured immediately before that replay. Never continue a
    // transaction whose internal source of truth could not be read.
    g_hudMaskPinSuspended.store(true, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    RestoreBlurBestEffort("HUD-mask transaction fail-open");
    if (vanillaState && vanillaState->captured
        && !RestoreHudVisibilitySnapshot(*vanillaState, "vanilla-mask-fail-open"))
        Log("HUD-mask transaction fail-open could not restore captured vanilla presentation");
    g_cleanHidden.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(0, std::memory_order_release);
    g_swallowPauseRelease.store(false, std::memory_order_release);
    g_swallowResumeRelease.store(false, std::memory_order_release);
    ResetHudSnapshots();
    g_hudMaskPinSuspended.store(false, std::memory_order_release);
    Log("C_UIHudMask transaction fail-open: %s", reason ? reason : "unknown");
}

void ReconcileHudMaskMutation()
{
    // The mask callback can be entered through generic engine dispatch. Validate the
    // thread before touching the non-atomic snapshot structs or mutating Flash.
    if (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId) {
        if (!g_hudMaskThreadMismatchLogged.exchange(true, std::memory_order_acq_rel))
            Log("C_UIHudMask mutation observed off validated main thread; transactional HUD pin skipped");
        return;
    }
    if (!ShouldPinGameplayHudPresentation())
        return;

    // Vanilla has already updated its internal C_UIHudMask state. A fresh complete
    // internal snapshot is mandatory before changing Flash presentation; otherwise
    // fail open while the just-applied vanilla Flash state is still intact.
    HudVisibilitySnapshot vanillaState{};
    if (!CaptureVanillaHudFromInternalMask(vanillaState)) {
        FailOpenHudMaskTransaction(nullptr, "authoritative internal HUD state unavailable");
        return;
    }
    g_vanillaPauseHudSnapshot = vanillaState;

    // Only presentation is rolled back. If that replay itself fails part-way, restore
    // the authoritative vanilla snapshot before releasing Menu rendering.
    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-mask-transaction")) {
        FailOpenHudMaskTransaction(&vanillaState, "gameplay HUD presentation replay failed");
        return;
    }
}

'''
native = replace_once(native, old_reconcile, new_reconcile, "strict mask transaction fail-open")
native = replace_once(
    native,
    '''    g_hudMaskTransactionAvailable.store(maskAvailable, std::memory_order_release);
    if (!maskAvailable)
        Log("C_UIHudMask transaction unavailable; using snapshot restore fallback");
''',
    '''    g_hudMaskTransactionAvailable.store(maskAvailable, std::memory_order_release);
    if (maskAvailable)
        Log("C_UIHudMask transaction active for hud=%p", hud);
    else
        Log("C_UIHudMask transaction unavailable; using snapshot restore fallback");
''',
    "transaction availability log",
)
old_entry = '''    const bool transactional =
        g_hudMaskTransactionAvailable.load(std::memory_order_acquire);
    if (transactional && !g_vanillaPauseHudSnapshot.captured)
        CaptureVanillaHudFromInternalMask(g_vanillaPauseHudSnapshot);
    if (!transactional
'''
new_entry = '''    const bool transactional =
        g_hudMaskTransactionAvailable.load(std::memory_order_acquire);
    if (transactional) {
        // Entry is accepted only with a fresh authoritative internal state. This makes
        // the later visible-menu handoff recoverable even if discovery fails afterwards.
        HudVisibilitySnapshot currentVanilla{};
        if (!CaptureVanillaHudFromInternalMask(currentVanilla)) {
            g_hudMaskPinSuspended.store(true, std::memory_order_release);
            if (g_vanillaPauseHudSnapshot.captured)
                RestoreHudVisibilitySnapshot(
                    g_vanillaPauseHudSnapshot, "vanilla-entry-read-fail-open");
            ResetHudSnapshots();
            g_hudMaskPinSuspended.store(false, std::memory_order_release);
            Log("vanilla pause opened but authoritative C_UIHudMask state could not be read; leaving ordinary visible pause menu (fail-open)");
            return false;
        }
        g_vanillaPauseHudSnapshot = currentVanilla;
    }
    if (!transactional
'''
native = replace_once(native, old_entry, new_entry, "strict transactional entry")
native = replace_once(
    native,
    '''        Forward(input, event, force);
        if (!TryEnterCleanPause("Escape/Start press", true))
            ArmPendingPauseAttempt();
        return;
''',
    '''        Forward(input, event, force);
        if (!TryEnterCleanPause("Escape/Start press", true)
            && g_gameplayHudSnapshot.captured)
            ArmPendingPauseAttempt();
        return;
''',
    "hard-fail press must not rearm",
)
native = replace_once(
    native,
    '''        Forward(input, event, force);
        if (!TryEnterCleanPause("Escape/Start release", false))
            ArmPendingPauseAttempt();
        return;
''',
    '''        Forward(input, event, force);
        if (!TryEnterCleanPause("Escape/Start release", false)
            && g_gameplayHudSnapshot.captured)
            ArmPendingPauseAttempt();
        return;
''',
    "hard-fail release must not rearm",
)
NATIVE_PATH.write_text(native, encoding="utf-8")

test = TEST_PATH.read_text(encoding="utf-8")
insert_before = '''    def test_vanilla_mutation_runs_before_visual_reconciliation(self):
'''
new_tests = '''    def test_global_method_hooks_filter_to_the_discovered_hud_mask_instance(self):
        self.assertIn('std::atomic<void*> g_maskObject{nullptr};', MASK)
        self.assertIn('std::atomic<void*> g_sourceMonitorObject{nullptr};', MASK)
        source = MASK[MASK.index('void __fastcall HookSourceEvent'):MASK.index('void __fastcall HookOnModuleMessage')]
        self.assertIn('sourceMonitor == g_sourceMonitorObject.load', source)
        module = MASK[MASK.index('void __fastcall HookOnModuleMessage'):MASK.index('} // namespace\\n\\nbool EnsureHooks')]
        self.assertIn('mask == g_maskObject.load', module)
        ensure = MASK[MASK.index('bool EnsureHooks'):MASK.index('bool ReadCurrentVisibility')]
        self.assertLess(ensure.index('g_maskObject.store'), ensure.index('g_observer.store'))
        self.assertLess(ensure.index('g_sourceMonitorObject.store'), ensure.index('g_observer.store'))

    def test_transaction_fails_open_when_authoritative_state_is_unavailable(self):
        callback = NATIVE[NATIVE.index('void FailOpenHudMaskTransaction'):NATIVE.index('void FailOpenHudMaintenance')]
        reconcile = callback[callback.index('void ReconcileHudMaskMutation'):]
        self.assertIn('if (!CaptureVanillaHudFromInternalMask(vanillaState))', reconcile)
        self.assertIn('FailOpenHudMaskTransaction(nullptr', reconcile)
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
        self.assertEqual(post.count('&& g_gameplayHudSnapshot.captured)\\n            ArmPendingPauseAttempt();'), 2)

'''
test = replace_once(test, insert_before, new_tests + insert_before, "final transaction tests")
TEST_PATH.write_text(test, encoding="utf-8")

validator = VALIDATOR_PATH.read_text(encoding="utf-8")
validator = replace_once(
    validator,
    '''if "if (refresh)\\n        NotifyAfterMutation();" not in module_hook:
    raise SystemExit("OnModuleMessage observer must run only for verified HUD refresh message 52")

transaction = native[native.index("void ReconcileHudMaskMutation"):native.index("void FailOpenHudMaintenance")]
''',
    '''if "if (refresh)\\n        NotifyAfterMutation();" not in module_hook:
    raise SystemExit("OnModuleMessage observer must run only for verified HUD refresh message 52")
for needle in (
    "std::atomic<void*> g_maskObject{nullptr};",
    "std::atomic<void*> g_sourceMonitorObject{nullptr};",
    "mask == g_maskObject.load",
    "sourceMonitor == g_sourceMonitorObject.load",
):
    if needle not in mask:
        raise SystemExit(f"global HUD-mask method hook is not target-instance scoped: {needle}")
ensure_mask = mask[mask.index("bool EnsureHooks"):mask.index("bool ReadCurrentVisibility")]
if ensure_mask.index("g_maskObject.store") > ensure_mask.index("g_observer.store"):
    raise SystemExit("target HUD-mask identity must be published before mutation observer")
if ensure_mask.index("g_sourceMonitorObject.store") > ensure_mask.index("g_observer.store"):
    raise SystemExit("target source-monitor identity must be published before mutation observer")

transaction = native[native.index("void ReconcileHudMaskMutation"):native.index("void FailOpenHudMaintenance")]
''',
    "validator object identity",
)
validator = replace_once(
    validator,
    '''if transaction.index("GetCurrentThreadId()") > transaction.index("ShouldPinGameplayHudPresentation()"):
    raise SystemExit("HUD-mask callback must validate thread before reading non-atomic snapshot state")

required_blur = (
''',
    '''if transaction.index("GetCurrentThreadId()") > transaction.index("ShouldPinGameplayHudPresentation()"):
    raise SystemExit("HUD-mask callback must validate thread before reading non-atomic snapshot state")
if "if (!CaptureVanillaHudFromInternalMask(vanillaState))" not in transaction:
    raise SystemExit("HUD-mask visual replay must require a fresh authoritative internal snapshot")
if "FailOpenHudMaskTransaction(nullptr" not in transaction or "FailOpenHudMaskTransaction(&vanillaState" not in transaction:
    raise SystemExit("HUD-mask transaction must fail open on internal-read or gameplay-replay failure")

required_blur = (
''',
    "validator strict fail-open",
)
validator = replace_once(
    validator,
    '''if "const bool transactional" not in enter or "if (!transactional" not in enter:
    raise SystemExit("vanilla Flash snapshot may be required only in non-transaction fallback mode")

hidden = native[native.index("void HandleHiddenInput"):native.index("void __fastcall HookPostInputEvent")]
''',
    '''if "const bool transactional" not in enter or "if (!transactional" not in enter:
    raise SystemExit("vanilla Flash snapshot may be required only in non-transaction fallback mode")
entry_transactional = enter[enter.index("if (transactional)"):enter.index("if (!transactional")]
if "if (!CaptureVanillaHudFromInternalMask(currentVanilla))" not in entry_transactional or "return false;" not in entry_transactional:
    raise SystemExit("transactional Clean Pause entry must require fresh internal HUD state")

hidden = native[native.index("void HandleHiddenInput"):native.index("void __fastcall HookPostInputEvent")]
''',
    "validator strict entry",
)
validator = replace_once(
    validator,
    '''pending = native[native.index("bool PendingAttemptAlive"):native.index("bool TryEnterCleanPause")]
if pending.index("RestoreVanillaHudPresentation") > pending.index("ResetHudSnapshots"):
    raise SystemExit("pending-entry expiry must undo any pre-ownership visual pin before reset")

print("stable native Clean Pause contract passed")
''',
    '''pending = native[native.index("bool PendingAttemptAlive"):native.index("bool TryEnterCleanPause")]
if pending.index("RestoreVanillaHudPresentation") > pending.index("ResetHudSnapshots"):
    raise SystemExit("pending-entry expiry must undo any pre-ownership visual pin before reset")

post = native[native.index("void __fastcall HookPostInputEvent"):native.index("bool InstallInputHook")]
if post.count("&& g_gameplayHudSnapshot.captured)\\n            ArmPendingPauseAttempt();") != 2:
    raise SystemExit("terminal Clean Pause entry failures must not re-arm pending ownership")

print("stable native Clean Pause contract passed")
''',
    "validator terminal failure rearm",
)
VALIDATOR_PATH.write_text(validator, encoding="utf-8")
