from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
native_path = ROOT / "native/src/clean_pause_native.cpp"
test_path = ROOT / "tests/test_hud_mask_transaction_contract.py"
validator_path = ROOT / "tools/validate_native_contract.py"


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, got {count}")
    return text.replace(old, new, 1)

native = native_path.read_text(encoding="utf-8")

old = '''    // Vanilla has already updated its internal C_UIHudMask state. Keep that state as
    // the source of truth and only roll the Flash presentation back before render.
    // The vanilla state is read live from I_UIHudMask when presentation is relinquished;
    // never snapshot all 28 Flash clips from a potentially partial source-event batch.
    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-mask-transaction"))
        Log("C_UIHudMask transaction could not restore gameplay HUD before render; periodic fallback remains active");
'''
new = '''    // Vanilla has already updated its internal C_UIHudMask state. Snapshot that
    // authoritative 28-element state (not the partially-mutated Flash presentation)
    // so a later discovery failure can still relinquish Clean Pause safely.
    HudVisibilitySnapshot vanillaState{};
    if (CaptureVanillaHudFromInternalMask(vanillaState))
        g_vanillaPauseHudSnapshot = vanillaState;

    // Only presentation is rolled back. KCD2 keeps owning the internal pause state.
    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-mask-transaction"))
        Log("C_UIHudMask transaction could not restore gameplay HUD before render; periodic fallback remains active");
'''
native = replace_once(native, old, new, "internal vanilla fallback snapshot")

old = '''    if (element != g_hudElement
        || !g_cleanHidden.load(std::memory_order_acquire)
        || g_hudMaskPinSuspended.load(std::memory_order_acquire))
        return;

    if (GetCurrentThreadId() != g_mainThreadId) {
        if (!g_hudUpdateThreadMismatchLogged.exchange(true, std::memory_order_acq_rel))
            Log("hud@0 Update observed off validated main thread; periodic HUD restore disabled for safety");
        return;
    }

    const ULONGLONG enteredAt = g_cleanHiddenSinceMs.load(std::memory_order_acquire);
    const ULONGLONG now = GetTickCount64();
'''
new = '''    if (element != g_hudElement)
        return;

    if (GetCurrentThreadId() != g_mainThreadId) {
        if (!g_hudUpdateThreadMismatchLogged.exchange(true, std::memory_order_acq_rel))
            Log("hud@0 Update observed off validated main thread; HUD maintenance disabled for safety");
        return;
    }

    const ULONGLONG now = GetTickCount64();

    // The no-blink transaction starts while pause entry is still pending. If Menu@0
    // never becomes verifiable and no further input arrives, expire that transaction
    // here on the already-proven main-thread HUD update path so gameplay presentation
    // cannot remain pinned indefinitely.
    if (!g_cleanHidden.load(std::memory_order_acquire)) {
        if (g_pendingPauseAttempt.load(std::memory_order_acquire)) {
            const ULONGLONG deadline = g_pendingDeadlineMs.load(std::memory_order_acquire);
            if (deadline != 0 && now > deadline) {
                g_hudMaskPinSuspended.store(true, std::memory_order_release);
                g_pendingPauseAttempt.store(false, std::memory_order_release);
                g_pendingDeadlineMs.store(0, std::memory_order_release);
                if (g_hudMaskTransactionAvailable.load(std::memory_order_acquire)
                    && g_gameplayHudSnapshot.captured
                    && !RestoreVanillaHudPresentation("vanilla-pending-timeout-update"))
                    Log("pending Clean Pause HUD-update timeout could not restore vanilla presentation");
                ResetHudSnapshots();
                g_hudMaskPinSuspended.store(false, std::memory_order_release);
                Log("pending Clean Pause presentation transaction expired on hud@0 Update");
            }
        }
        return;
    }

    if (g_hudMaskPinSuspended.load(std::memory_order_acquire))
        return;

    const ULONGLONG enteredAt = g_cleanHiddenSinceMs.load(std::memory_order_acquire);
'''
native = replace_once(native, old, new, "pending timeout main-thread cleanup")

old = '''    if (!g_gameplayHudSnapshot.captured) {
        ResetHudSnapshots();
        Log("vanilla pause opened but gameplay HUD state was unavailable; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    const bool transactional =
        g_hudMaskTransactionAvailable.load(std::memory_order_acquire);
    if (!transactional
'''
new = '''    if (!g_gameplayHudSnapshot.captured) {
        ResetHudSnapshots();
        Log("vanilla pause opened but gameplay HUD state was unavailable; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    const bool transactional =
        g_hudMaskTransactionAvailable.load(std::memory_order_acquire);
    if (transactional && !g_vanillaPauseHudSnapshot.captured)
        CaptureVanillaHudFromInternalMask(g_vanillaPauseHudSnapshot);
    if (!transactional
'''
native = replace_once(native, old, new, "entry internal fallback capture")
native_path.write_text(native, encoding="utf-8")

test = test_path.read_text(encoding="utf-8")
needle = '''    def test_transaction_never_whole_snapshots_partial_flash_state(self):
        callback = NATIVE[NATIVE.index('void ReconcileHudMaskMutation()'):NATIVE.index('void FailOpenHudMaintenance')]
        self.assertNotIn('CaptureHudVisibilitySnapshot', callback)
        self.assertNotIn('g_vanillaPauseHudSnapshot =', callback)
        self.assertIn('RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot', callback)
        self.assertLess(callback.index('GetCurrentThreadId()'), callback.index('ShouldPinGameplayHudPresentation()'))
'''
replacement = '''    def test_transaction_never_whole_snapshots_partial_flash_state(self):
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
'''
test = replace_once(test, needle, replacement, "transaction contract update")
test_path.write_text(test, encoding="utf-8")

validator = validator_path.read_text(encoding="utf-8")
old = '''if "CaptureHudVisibilitySnapshot" in transaction or "g_vanillaPauseHudSnapshot =" in transaction:
    raise SystemExit("partial HUD-mask callbacks must not snapshot the whole Flash HUD as vanilla state")
if "RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot" not in transaction:
'''
new = '''if "CaptureHudVisibilitySnapshot" in transaction:
    raise SystemExit("partial HUD-mask callbacks must not snapshot the whole Flash HUD as vanilla state")
if "CaptureVanillaHudFromInternalMask" not in transaction or "g_vanillaPauseHudSnapshot = vanillaState;" not in transaction:
    raise SystemExit("HUD-mask callback must retain an authoritative internal-state fallback snapshot")
if "RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot" not in transaction:
'''
validator = replace_once(validator, old, new, "validator internal snapshot")
old = '''hud_update = native[native.index("void __fastcall HookHudUpdate"):native.index("bool EnsureHudUpdateHook")]
if "g_hudMaskPinSuspended.load(std::memory_order_acquire)" not in hud_update:
    raise SystemExit("periodic HUD fallback must honor transactional exit suspension")

pending = native[native.index("bool PendingAttemptAlive"):native.index("bool TryEnterCleanPause")]
'''
new = '''hud_update = native[native.index("void __fastcall HookHudUpdate"):native.index("bool EnsureHudUpdateHook")]
if "g_hudMaskPinSuspended.load(std::memory_order_acquire)" not in hud_update:
    raise SystemExit("periodic HUD fallback must honor transactional exit suspension")
for needle in (
    "g_pendingPauseAttempt.load(std::memory_order_acquire)",
    "now > deadline",
    'RestoreVanillaHudPresentation("vanilla-pending-timeout-update")',
):
    if needle not in hud_update:
        raise SystemExit(f"pending no-input timeout cleanup missing from HUD update: {needle}")

pending = native[native.index("bool PendingAttemptAlive"):native.index("bool TryEnterCleanPause")]
'''
validator = replace_once(validator, old, new, "validator pending timeout")
validator_path.write_text(validator, encoding="utf-8")
