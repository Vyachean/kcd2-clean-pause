from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
native_path = ROOT / "native/src/clean_pause_native.cpp"
test_path = ROOT / "tests/test_hud_mask_transaction_contract.py"

native = native_path.read_text(encoding="utf-8")

replacements = [
    (
        "std::atomic_bool g_pendingPauseAttempt{false};\nstd::atomic_ullong g_pendingDeadlineMs{0};",
        "std::atomic_bool g_pendingPauseAttempt{false};\nstd::atomic_ullong g_pendingDeadlineMs{0};\nstd::atomic_bool g_hudMaskPinSuspended{false};",
    ),
    (
        "bool ShouldPinGameplayHudPresentation()\n{\n    if (!g_gameplayHudSnapshot.captured)",
        "bool ShouldPinGameplayHudPresentation()\n{\n    if (g_hudMaskPinSuspended.load(std::memory_order_acquire))\n        return false;\n    if (!g_gameplayHudSnapshot.captured)",
    ),
    (
        "    HudVisibilitySnapshot vanillaState{};\n    if (!CaptureHudVisibilitySnapshot(vanillaState, \"vanilla-mask-transaction\")) {\n        Log(\"C_UIHudMask transaction could not capture vanilla HUD state; periodic fallback remains active\");\n        return;\n    }\n    g_vanillaPauseHudSnapshot = vanillaState;\n\n    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, \"gameplay-mask-transaction\"))",
        "    // Capture vanilla presentation only while the initial pause transition is pending.\n    // Once Clean Pause owns presentation, later HUD-mask callbacks must not overwrite\n    // the saved vanilla-pause state with the already-pinned gameplay presentation.\n    if (!g_cleanHidden.load(std::memory_order_acquire)) {\n        HudVisibilitySnapshot vanillaState{};\n        if (!CaptureHudVisibilitySnapshot(vanillaState, \"vanilla-mask-transaction\")) {\n            Log(\"C_UIHudMask transaction could not capture vanilla HUD state; periodic fallback remains active\");\n            return;\n        }\n        g_vanillaPauseHudSnapshot = vanillaState;\n    }\n\n    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, \"gameplay-mask-transaction\"))",
    ),
    (
        "    g_pendingPauseAttempt.store(false, std::memory_order_release);\n    g_pendingDeadlineMs.store(0, std::memory_order_release);\n    ResetHudSnapshots();\n    if (reason)",
        "    g_pendingPauseAttempt.store(false, std::memory_order_release);\n    g_pendingDeadlineMs.store(0, std::memory_order_release);\n    g_hudMaskPinSuspended.store(false, std::memory_order_release);\n    ResetHudSnapshots();\n    if (reason)",
    ),
    (
        "        if (pressed) {\n            RestoreBlurBestEffort(\"show vanilla pause via Escape/Start\");\n            if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, \"vanilla-pause-visible-menu\"))\n                Log(\"could not restore captured vanilla-pause HUD before showing Menu; continuing fail-open\");\n            g_cleanHidden.store(false, std::memory_order_release);\n            g_renderSuppressionObserved.store(false, std::memory_order_release);\n            g_cleanHiddenSinceMs.store(0, std::memory_order_release);\n            ResetHudSnapshots();\n            g_swallowPauseRelease.store(true, std::memory_order_release);",
        "        if (pressed) {\n            // Stop the HUD-mask observer from re-pinning gameplay while the saved\n            // vanilla pause presentation is being restored. Keep Menu rendering\n            // suppressed until that restore is complete, then relinquish ownership.\n            g_hudMaskPinSuspended.store(true, std::memory_order_release);\n            g_pendingPauseAttempt.store(false, std::memory_order_release);\n            g_pendingDeadlineMs.store(0, std::memory_order_release);\n            RestoreBlurBestEffort(\"show vanilla pause via Escape/Start\");\n            if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, \"vanilla-pause-visible-menu\"))\n                Log(\"could not restore captured vanilla-pause HUD before showing Menu; continuing fail-open\");\n            g_cleanHidden.store(false, std::memory_order_release);\n            g_renderSuppressionObserved.store(false, std::memory_order_release);\n            g_cleanHiddenSinceMs.store(0, std::memory_order_release);\n            ResetHudSnapshots();\n            g_hudMaskPinSuspended.store(false, std::memory_order_release);\n            g_swallowPauseRelease.store(true, std::memory_order_release);",
    ),
    (
        "        RestoreBlurBestEffort(\"show vanilla pause via B\");\n        if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, \"vanilla-pause-visible-menu-via-B\"))",
        "        g_hudMaskPinSuspended.store(true, std::memory_order_release);\n        g_pendingPauseAttempt.store(false, std::memory_order_release);\n        g_pendingDeadlineMs.store(0, std::memory_order_release);\n        RestoreBlurBestEffort(\"show vanilla pause via B\");\n        if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, \"vanilla-pause-visible-menu-via-B\"))",
    ),
    (
        "        g_pendingPauseAttempt.store(false, std::memory_order_release);\n        g_pendingDeadlineMs.store(0, std::memory_order_release);\n        ResetHudSnapshots();\n        g_swallowResumeRelease.store(true, std::memory_order_release);",
        "        g_pendingPauseAttempt.store(false, std::memory_order_release);\n        g_pendingDeadlineMs.store(0, std::memory_order_release);\n        ResetHudSnapshots();\n        g_hudMaskPinSuspended.store(false, std::memory_order_release);\n        g_swallowResumeRelease.store(true, std::memory_order_release);",
    ),
]

for old, new in replacements:
    if native.count(old) != 1:
        raise SystemExit(f"native guard mismatch: expected exactly one occurrence of {old[:80]!r}, got {native.count(old)}")
    native = native.replace(old, new, 1)

native_path.write_text(native, encoding="utf-8")

test = test_path.read_text(encoding="utf-8")
needle = "    def test_entry_reuses_transactionally_captured_vanilla_state(self):\n"
if test.count(needle) != 1:
    raise SystemExit("test insertion guard mismatch")
insert = '''    def test_clean_pause_exit_suspends_mask_pin_before_vanilla_restore(self):\n        hidden = NATIVE[NATIVE.index('void HandleHiddenInput'):NATIVE.index('void __fastcall HookPostInputEvent')]\n        start = hidden[hidden.index('if (IsPauseKey(key))'):hidden.index('if (key == KeyId::XiB)')]\n        self.assertLess(start.index('g_hudMaskPinSuspended.store(true'), start.index('RestoreHudVisibilitySnapshot'))\n        self.assertLess(start.index('RestoreHudVisibilitySnapshot'), start.index('g_cleanHidden.store(false'))\n        self.assertLess(start.index('g_cleanHidden.store(false'), start.index('g_hudMaskPinSuspended.store(false'))\n\n        b_path = hidden[hidden.index('if (key == KeyId::XiB)'):]\n        self.assertLess(b_path.index('g_hudMaskPinSuspended.store(true'), b_path.index('RestoreHudVisibilitySnapshot'))\n        self.assertLess(b_path.index('RestoreHudVisibilitySnapshot'), b_path.index('g_cleanHidden.store(false'))\n        self.assertLess(b_path.index('g_cleanHidden.store(false'), b_path.index('g_hudMaskPinSuspended.store(false'))\n\n    def test_vanilla_snapshot_is_not_overwritten_after_clean_pause_entry(self):\n        callback = NATIVE[NATIVE.index('void ReconcileHudMaskMutation()'):NATIVE.index('void FailOpenHudMaintenance')]\n        self.assertIn('if (!g_cleanHidden.load(std::memory_order_acquire))', callback)\n        capture = callback.index('CaptureHudVisibilitySnapshot')\n        guard = callback.index('if (!g_cleanHidden.load(std::memory_order_acquire))')\n        restore = callback.index('RestoreHudVisibilitySnapshot')\n        self.assertLess(guard, capture)\n        self.assertLess(capture, restore)\n\n'''
test = test.replace(needle, insert + needle, 1)
test_path.write_text(test, encoding="utf-8")
