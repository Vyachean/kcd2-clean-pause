from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one guarded replacement, got {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Runtime state: separate long-lived input correlation from the very short period
# in which vanilla PauseGame is actually mutating pause/HUD state.
replace_once(
    "native/src/clean_pause_native.cpp",
    '''std::atomic_bool g_pauseBarrierObserved{false};\nDWORD g_mainThreadId{};''',
    '''std::atomic_bool g_pauseBarrierObserved{false};\nstd::atomic_bool g_pauseTransitionActive{false};\nstd::atomic_ullong g_pausePressAtMs{0};\nDWORD g_mainThreadId{};''',
)

replace_once(
    "native/src/clean_pause_native.cpp",
    '''    bool freeze = g_cleanHidden.load(std::memory_order_acquire);\n    if (!freeze && g_pendingPauseAttempt.load(std::memory_order_acquire)) {\n        const ULONGLONG deadline = g_pendingDeadlineMs.load(std::memory_order_acquire);\n        freeze = deadline != 0 && GetTickCount64() <= deadline;\n    }\n    if (!freeze)\n        return false;\n''',
    '''    // Pending input correlation alone must not mutate/freeze HUD presentation.\n    // Only the actual vanilla PauseGame transition and established Clean Pause own\n    // this narrow presentation freeze window.\n    const bool freeze = g_cleanHidden.load(std::memory_order_acquire)\n        || g_pauseTransitionActive.load(std::memory_order_acquire);\n    if (!freeze)\n        return false;\n''',
)

replace_once(
    "native/src/clean_pause_native.cpp",
    '''    g_pauseBarrierObserved.store(false, std::memory_order_release);\n}\n''',
    '''    g_pauseBarrierObserved.store(false, std::memory_order_release);\n    g_pauseTransitionActive.store(false, std::memory_order_release);\n}\n''',
)

replace_once(
    "native/src/clean_pause_native.cpp",
    '''    if (g_cleanHidden.load(std::memory_order_acquire))\n        return true;\n    if (!g_pendingPauseAttempt.load(std::memory_order_acquire))\n        return false;\n\n    const ULONGLONG deadline = g_pendingDeadlineMs.load(std::memory_order_acquire);\n    return deadline != 0 && GetTickCount64() <= deadline;\n''',
    '''    if (g_cleanHidden.load(std::memory_order_acquire))\n        return true;\n\n    // Do not replay 28 Flash clips during the physical press/release correlation\n    // window. Arm transactional pinning only when the verified vanilla PauseGame call\n    // itself begins; this keeps the no-blink protection in the mutation call stack\n    // without stalling gameplay presentation before the real pause starts.\n    return g_pauseTransitionActive.load(std::memory_order_acquire);\n''',
)

# Pending expiry should undo presentation only if the actual PauseGame transition had
# started; ordinary pre-pause correlation has not pinned anything anymore.
replace_once(
    "native/src/clean_pause_native.cpp",
    '''    g_hudMaskPinSuspended.store(true, std::memory_order_release);\n    g_pendingPauseAttempt.store(false, std::memory_order_release);\n    g_pendingDeadlineMs.store(0, std::memory_order_release);\n    if (g_gameplayHudSnapshot.captured\n        && !RestoreVanillaHudPresentation("vanilla-pending-expiry"))\n        Log("pending Clean Pause expiry could not restore current vanilla HUD presentation");\n    ResetHudSnapshots();\n''',
    '''    g_hudMaskPinSuspended.store(true, std::memory_order_release);\n    const bool transitionWasActive =\n        g_pauseTransitionActive.exchange(false, std::memory_order_acq_rel);\n    g_pendingPauseAttempt.store(false, std::memory_order_release);\n    g_pendingDeadlineMs.store(0, std::memory_order_release);\n    if (transitionWasActive && g_gameplayHudSnapshot.captured\n        && !RestoreVanillaHudPresentation("vanilla-pending-expiry"))\n        Log("pending Clean Pause expiry could not restore current vanilla HUD presentation");\n    ResetHudSnapshots();\n''',
)

replace_once(
    "native/src/clean_pause_native.cpp",
    '''                g_hudMaskPinSuspended.store(true, std::memory_order_release);\n                g_pendingPauseAttempt.store(false, std::memory_order_release);\n                g_pendingDeadlineMs.store(0, std::memory_order_release);\n                if (g_hudMaskTransactionAvailable.load(std::memory_order_acquire)\n                    && g_gameplayHudSnapshot.captured\n                    && !RestoreVanillaHudPresentation("vanilla-pending-timeout-update"))\n                    Log("pending Clean Pause HUD-update timeout could not restore vanilla presentation");\n''',
    '''                g_hudMaskPinSuspended.store(true, std::memory_order_release);\n                const bool transitionWasActive =\n                    g_pauseTransitionActive.exchange(false, std::memory_order_acq_rel);\n                g_pendingPauseAttempt.store(false, std::memory_order_release);\n                g_pendingDeadlineMs.store(0, std::memory_order_release);\n                if (transitionWasActive\n                    && g_hudMaskTransactionAvailable.load(std::memory_order_acquire)\n                    && g_gameplayHudSnapshot.captured\n                    && !RestoreVanillaHudPresentation("vanilla-pending-timeout-update"))\n                    Log("pending Clean Pause HUD-update timeout could not restore vanilla presentation");\n''',
)

# Clean Pause becomes the owner before the short transition flag is dropped, leaving
# no gap in which mask mutations could escape presentation pinning.
replace_once(
    "native/src/clean_pause_native.cpp",
    '''    g_cleanHidden.store(true, std::memory_order_release);\n    g_swallowPauseRelease.store(swallowMatchingRelease, std::memory_order_release);\n''',
    '''    g_cleanHidden.store(true, std::memory_order_release);\n    g_pauseTransitionActive.store(false, std::memory_order_release);\n    g_swallowPauseRelease.store(swallowMatchingRelease, std::memory_order_release);\n''',
)

# Instrument one physical transition without per-frame logging.
replace_once(
    "native/src/clean_pause_native.cpp",
    '''    if (pressed) {\n        ResetHudSnapshots();\n''',
    '''    if (pressed) {\n        const ULONGLONG pressAt = GetTickCount64();\n        g_pausePressAtMs.store(pressAt, std::memory_order_release);\n        Log("pause physical press: key=%u name=%s state=0x%08x",\n            static_cast<unsigned>(key),\n            event->keyName ? event->keyName : "<null>",\n            static_cast<unsigned>(event->state));\n        ResetHudSnapshots();\n''',
)

replace_once(
    "native/src/clean_pause_native.cpp",
    '''        ArmPendingPauseAttempt();\n        g_pauseBarrierObserved.store(false, std::memory_order_release);\n        Forward(input, event, force);\n\n        // Preferred path: vanilla itself called and returned from PauseGame(true)\n''',
    '''        ArmPendingPauseAttempt();\n        g_pauseBarrierObserved.store(false, std::memory_order_release);\n        const ULONGLONG dispatchAt = GetTickCount64();\n        Log("pause press preparation complete; setupMs=%llu",\n            static_cast<unsigned long long>(dispatchAt - pressAt));\n        Forward(input, event, force);\n        Log("pause press vanilla dispatch returned; dispatchMs=%llu",\n            static_cast<unsigned long long>(GetTickCount64() - dispatchAt));\n\n        // Preferred path: vanilla itself called and returned from PauseGame(true)\n''',
)

replace_once(
    "native/src/clean_pause_native.cpp",
    '''            if (!TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)\n                && g_gameplayHudSnapshot.captured)\n                ArmPendingPauseAttempt();\n            return;\n''',
    '''            if (!TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)\n                && g_gameplayHudSnapshot.captured)\n                ArmPendingPauseAttempt();\n            g_pauseTransitionActive.store(false, std::memory_order_release);\n            return;\n''',
)

replace_once(
    "native/src/clean_pause_native.cpp",
    '''    if (released && PendingAttemptAlive()) {\n        Forward(input, event, force);\n        if (!TryEnterCleanPause("Escape/Start release", false)\n            && g_gameplayHudSnapshot.captured)\n            ArmPendingPauseAttempt();\n        return;\n    }\n''',
    '''    if (released && PendingAttemptAlive()) {\n        const ULONGLONG releaseAt = GetTickCount64();\n        const ULONGLONG pressAt = g_pausePressAtMs.load(std::memory_order_acquire);\n        Log("pause physical release: key=%u sincePressMs=%llu",\n            static_cast<unsigned>(key),\n            static_cast<unsigned long long>(pressAt ? releaseAt - pressAt : 0));\n        Forward(input, event, force);\n        const bool barrier =\n            g_pauseBarrierObserved.exchange(false, std::memory_order_acq_rel);\n        Log("pause release vanilla dispatch returned; dispatchMs=%llu barrier=%s",\n            static_cast<unsigned long long>(GetTickCount64() - releaseAt),\n            barrier ? "true" : "false");\n\n        bool entered{};\n        if (barrier)\n            entered = TryEnterCleanPause(\n                "vanilla PauseGame barrier after Escape/Start release", false, false);\n        else\n            entered = TryEnterCleanPause("Escape/Start release", false);\n        if (!entered && g_gameplayHudSnapshot.captured)\n            ArmPendingPauseAttempt();\n        g_pauseTransitionActive.store(false, std::memory_order_release);\n        return;\n    }\n''',
)

# Revert the disproven audio-fade override. The retail game already requested zero.
replace_once(
    "native/src/clean_pause_native.cpp",
    '''    // CryEngine defines the third PauseGame argument as the SFX/Voice fade-out\n    // duration. KCD2's non-zero fade is useful for its visible menu transition, but\n    // it leaves dialogue audible after the Clean Pause frame is already frozen. For\n    // the exact validated pending physical Clean Pause only, keep vanilla pause/force\n    // ownership unchanged and clamp that audio fade duration to zero. We still never\n    // synthesize a PauseGame call.\n    const unsigned int effectiveFadeOutInMs = observe ? 0u : fadeOutInMs;\n    if (g_originalPauseGame)\n        g_originalPauseGame(framework, pause, force, effectiveFadeOutInMs);\n\n    if (!observe || !g_pendingPauseAttempt.load(std::memory_order_acquire))\n        return;\n\n    g_pauseBarrierObserved.store(true, std::memory_order_release);\n    Log(\n        "vanilla IGameFramework::PauseGame(true) returned during pending pause; force=%s requestedFadeMs=%u effectiveFadeMs=%u callMs=%llu",\n        force ? "true" : "false",\n        fadeOutInMs,\n        effectiveFadeOutInMs,\n        static_cast<unsigned long long>(GetTickCount64() - enteredAt));\n''',
    '''    // Pending input correlation does not own presentation. Arm the narrow\n    // transaction only for the real vanilla pause call, so C_UIHudMask changes made\n    // inside PauseGame are rolled back in the same stack without doing 28-clip Flash\n    // work throughout the physical press/release window.\n    if (observe)\n        g_pauseTransitionActive.store(true, std::memory_order_release);\n\n    // KCD2 remains the sole pause owner and receives the exact vanilla arguments.\n    if (g_originalPauseGame)\n        g_originalPauseGame(framework, pause, force, fadeOutInMs);\n\n    if (!observe || !g_pendingPauseAttempt.load(std::memory_order_acquire)) {\n        if (observe)\n            g_pauseTransitionActive.store(false, std::memory_order_release);\n        return;\n    }\n\n    g_pauseBarrierObserved.store(true, std::memory_order_release);\n    const ULONGLONG pressAt = g_pausePressAtMs.load(std::memory_order_acquire);\n    Log(\n        "vanilla IGameFramework::PauseGame(true) returned during pending pause; force=%s fadeMs=%u callMs=%llu pressToPauseMs=%llu",\n        force ? "true" : "false",\n        fadeOutInMs,\n        static_cast<unsigned long long>(GetTickCount64() - enteredAt),\n        static_cast<unsigned long long>(pressAt ? enteredAt - pressAt : 0));\n''',
)

# Tests: exact vanilla args, narrow transition scope, release barrier and diagnostics.
replace_once(
    "tests/test_pause_barrier_contract.py",
    '''    def test_pause_hook_keeps_vanilla_pause_ownership_and_zeroes_only_clean_pause_audio_fade(self):\n        hook = NATIVE[NATIVE.index("void __fastcall HookPauseGame"):NATIVE.index("bool InstallPauseBarrierHook")]\n        self.assertIn("framework == g_gameFramework", hook)\n        self.assertIn("g_pendingPauseAttempt.load", hook)\n        self.assertIn("const unsigned int effectiveFadeOutInMs = observe ? 0u : fadeOutInMs;", hook)\n        self.assertIn("g_originalPauseGame(framework, pause, force, effectiveFadeOutInMs);", hook)\n        self.assertNotIn("g_originalPauseGame(framework, pause, force, fadeOutInMs);", hook)\n        self.assertIn("requestedFadeMs=%u effectiveFadeMs=%u", hook)\n        self.assertLess(hook.index("g_originalPauseGame("), hook.index("g_pauseBarrierObserved.store(true"))\n        self.assertEqual(NATIVE.count("g_originalPauseGame("), 1)\n''',
    '''    def test_pause_hook_keeps_exact_vanilla_ownership_and_scopes_pinning_to_pause_call(self):\n        hook = NATIVE[NATIVE.index("void __fastcall HookPauseGame"):NATIVE.index("bool InstallPauseBarrierHook")]\n        self.assertIn("framework == g_gameFramework", hook)\n        self.assertIn("g_pendingPauseAttempt.load", hook)\n        self.assertIn("g_pauseTransitionActive.store(true", hook)\n        self.assertIn("g_originalPauseGame(framework, pause, force, fadeOutInMs);", hook)\n        self.assertNotIn("effectiveFadeOutInMs", hook)\n        self.assertLess(hook.index("g_pauseTransitionActive.store(true"), hook.index("g_originalPauseGame("))\n        self.assertLess(hook.index("g_originalPauseGame("), hook.index("g_pauseBarrierObserved.store(true"))\n        self.assertEqual(NATIVE.count("g_originalPauseGame("), 1)\n\n    def test_pending_input_correlation_does_not_pin_or_freeze_hud(self):\n        freeze = NATIVE[NATIVE.index("bool ShouldFreezeHudFunction"):NATIVE.index("bool __fastcall HookHudCallFunction")]\n        pin = NATIVE[NATIVE.index("bool ShouldPinGameplayHudPresentation"):NATIVE.index("bool CaptureVanillaHudFromInternalMask")]\n        self.assertIn("g_pauseTransitionActive.load", freeze)\n        self.assertIn("g_pauseTransitionActive.load", pin)\n        self.assertNotIn("g_pendingPauseAttempt.load", freeze)\n        self.assertNotIn("g_pendingPauseAttempt.load", pin)\n\n    def test_release_consumes_pause_barrier_and_logs_transition_timing(self):\n        post = NATIVE[NATIVE.index("void __fastcall HookPostInputEvent"):NATIVE.index("bool ResolveGameFramework")]\n        self.assertIn("pause physical press:", post)\n        self.assertIn("pause press preparation complete; setupMs=%llu", post)\n        self.assertIn("pause physical release: key=%u sincePressMs=%llu", post)\n        self.assertIn("pause release vanilla dispatch returned; dispatchMs=%llu barrier=%s", post)\n        self.assertIn("vanilla PauseGame barrier after Escape/Start release", post)\n''',
)

# Validator follows the same architectural contract.
replace_once(
    "tools/validate_native_contract.py",
    '''if "const unsigned int effectiveFadeOutInMs = observe ? 0u : fadeOutInMs;" not in pause_hook:\n    raise SystemExit("pending Clean Pause must clamp only the documented SFX/Voice fade duration")\nif "g_originalPauseGame(framework, pause, force, effectiveFadeOutInMs);" not in pause_hook:\n    raise SystemExit("PauseGame hook must preserve vanilla pause/force ownership and use only the scoped audio fade override")\nif "requestedFadeMs=%u effectiveFadeMs=%u" not in pause_hook:\n    raise SystemExit("PauseGame log must expose requested and effective audio fade durations")\n''',
    '''if "g_pauseTransitionActive.store(true" not in pause_hook:\n    raise SystemExit("HUD transaction must arm only when the verified vanilla PauseGame call begins")\nif "g_originalPauseGame(framework, pause, force, fadeOutInMs);" not in pause_hook:\n    raise SystemExit("PauseGame observer must forward exact vanilla arguments unchanged")\nif "effectiveFadeOutInMs" in pause_hook:\n    raise SystemExit("disproven audio-fade override must not remain in production")\nif pause_hook.index("g_pauseTransitionActive.store(true") > pause_hook.index("g_originalPauseGame("):\n    raise SystemExit("pause transition pinning must arm before vanilla PauseGame mutates HUD")\n''',
)

replace_once(
    "tools/validate_native_contract.py",
    '''freeze = native[native.index("bool ShouldFreezeHudFunction"):native.index("bool __fastcall HookHudCallFunction")]\nif freeze.count("std::strcmp(") != 2:\n    raise SystemExit("subtitle freeze whitelist must contain exactly two comparisons")\n''',
    '''freeze = native[native.index("bool ShouldFreezeHudFunction"):native.index("bool __fastcall HookHudCallFunction")]\nif freeze.count("std::strcmp(") != 2:\n    raise SystemExit("subtitle freeze whitelist must contain exactly two comparisons")\nif "g_pauseTransitionActive.load" not in freeze or "g_pendingPauseAttempt.load" in freeze:\n    raise SystemExit("subtitle freeze must be scoped to actual PauseGame transition, not pending input correlation")\npin = native[native.index("bool ShouldPinGameplayHudPresentation"):native.index("bool CaptureVanillaHudFromInternalMask")]\nif "g_pauseTransitionActive.load" not in pin or "g_pendingPauseAttempt.load" in pin:\n    raise SystemExit("HUD pinning must be scoped to actual PauseGame transition, not pending input correlation")\n''',
)

replace_once(
    "tools/validate_native_contract.py",
    '''if 'TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)' not in post:\n    raise SystemExit("verified PauseGame barrier must accept Clean Pause without waiting for Menu visibility/release")\n''',
    '''if 'TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)' not in post:\n    raise SystemExit("verified PauseGame barrier must accept Clean Pause on press when vanilla pauses there")\nif '"vanilla PauseGame barrier after Escape/Start release", false, false' not in post:\n    raise SystemExit("verified PauseGame barrier must also be consumed on the retail Start-release pause path")\nfor needle in (\n    "pause physical press:",\n    "pause press preparation complete; setupMs=%llu",\n    "pause physical release: key=%u sincePressMs=%llu",\n    "pressToPauseMs=%llu",\n):\n    if needle not in native:\n        raise SystemExit(f"pause transition timing diagnostic missing: {needle}")\n''',
)

# Documentation: remove the falsified audio-fade theory and describe the narrow scope.
replace_once(
    "docs/DESIGN.md",
    '''2. observes the validated vanilla `IGameFramework::PauseGame(true, ...)` call as the preferred event barrier; the mod never calls `PauseGame` itself; for the exact pending Clean Pause transition it preserves vanilla `pause`/`force` ownership but clamps only the documented SFX/Voice fade duration to `0 ms`, so dialogue does not continue after the retained frame freezes;\n''',
    '''2. observes the validated vanilla `IGameFramework::PauseGame(true, ...)` call as the preferred event barrier; the mod never calls `PauseGame` itself and forwards its arguments unchanged; pending Start/Escape correlation alone does not pin HUD presentation, and the transactional HUD/subtitle freeze is armed only for the actual verified vanilla `PauseGame` call;\n''',
)

replace_once(
    "docs/DESIGN.md",
    '''The mask transaction can begin while pause entry is still pending, before `Menu@0` becomes verifiably visible. The preferred completion point is the return from KCD2's own validated `IGameFramework::PauseGame(true, ...)` call during the forwarded physical press. CryEngine documents the third `PauseGame` argument as the SFX/Voice fade-out time; only for this already-validated pending Clean Pause call the detour changes that duration to `0 ms`, while forwarding the original `pause` and `force` values unchanged. This removes the otherwise intentional audio tail after the visual frame has frozen. The detour records the barrier after vanilla returns; Clean Pause presentation is accepted after the outer `PostInputEvent` forwarding returns, avoiding re-entrant Flash/Lua work inside `PauseGame` itself. If no verified barrier is observed, the existing Menu-visibility path remains the compatibility fallback.''',
    '''The physical Start/Escape press first captures the gameplay snapshot and establishes only bounded input correlation; it does **not** start HUD replay or subtitle freezing. The presentation transaction is armed only when KCD2 enters its own validated `IGameFramework::PauseGame(true, ...)` call. This keeps same-call-stack protection for the actual pause HUD mutations while avoiding repeated 28-clip Flash work during the pre-pause press/release interval. The detour records the barrier after vanilla returns; Clean Pause presentation is accepted after the outer `PostInputEvent` forwarding returns, avoiding re-entrant Flash/Lua work inside `PauseGame` itself. Retail Xbox-controller evidence shows KCD2 may call `PauseGame(true)` on Start release rather than press, so the barrier is consumed on either physical phase. If no verified barrier is observed, the existing Menu-visibility path remains the compatibility fallback.''',
)

replace_once(
    "docs/DESIGN.md",
    '''IGameFramework::PauseGame            -> slot 13 (vanilla owner; pending Clean Pause audio fade -> 0 ms)\n''',
    '''IGameFramework::PauseGame            -> slot 13 (observer/barrier; exact vanilla arguments)\n''',
)

replace_once(
    "CHANGELOG.md",
    '''- Synchronizes Clean Pause audio with the retained frame by clamping only the pending Clean Pause `PauseGame` SFX/Voice fade duration to `0 ms`; KCD2 still owns the actual pause and the original `pause`/`force` values.\n''',
    '''- Narrows HUD/subtitle presentation pinning to the actual validated vanilla `PauseGame` transition instead of the whole Start press/release correlation window, avoiding unnecessary pre-pause Flash work while retaining same-stack no-blink protection.\n''',
)

Path(__file__).unlink()
print("PR34 transition-scope correction applied")
