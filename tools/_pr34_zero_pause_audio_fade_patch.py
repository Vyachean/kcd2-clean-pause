from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one guarded replacement, got {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "native/src/clean_pause_native.cpp",
    '''    // KCD2 remains the only pause owner. Never alter arguments and never synthesize a\n    // PauseGame call; observe only after the exact vanilla call has returned.\n    if (g_originalPauseGame)\n        g_originalPauseGame(framework, pause, force, fadeOutInMs);\n\n    if (!observe || !g_pendingPauseAttempt.load(std::memory_order_acquire))\n        return;\n\n    g_pauseBarrierObserved.store(true, std::memory_order_release);\n    Log(\n        "vanilla IGameFramework::PauseGame(true) returned during pending pause; force=%s fadeMs=%u callMs=%llu",\n        force ? "true" : "false",\n        fadeOutInMs,\n        static_cast<unsigned long long>(GetTickCount64() - enteredAt));\n''',
    '''    // CryEngine defines the third PauseGame argument as the SFX/Voice fade-out\n    // duration. KCD2's non-zero fade is useful for its visible menu transition, but\n    // it leaves dialogue audible after the Clean Pause frame is already frozen. For\n    // the exact validated pending physical Clean Pause only, keep vanilla pause/force\n    // ownership unchanged and clamp that audio fade duration to zero. We still never\n    // synthesize a PauseGame call.\n    const unsigned int effectiveFadeOutInMs = observe ? 0u : fadeOutInMs;\n    if (g_originalPauseGame)\n        g_originalPauseGame(framework, pause, force, effectiveFadeOutInMs);\n\n    if (!observe || !g_pendingPauseAttempt.load(std::memory_order_acquire))\n        return;\n\n    g_pauseBarrierObserved.store(true, std::memory_order_release);\n    Log(\n        "vanilla IGameFramework::PauseGame(true) returned during pending pause; force=%s requestedFadeMs=%u effectiveFadeMs=%u callMs=%llu",\n        force ? "true" : "false",\n        fadeOutInMs,\n        effectiveFadeOutInMs,\n        static_cast<unsigned long long>(GetTickCount64() - enteredAt));\n''',
)

replace_once(
    "tests/test_pause_barrier_contract.py",
    '''    def test_pause_hook_is_observer_only_and_after_original(self):\n        hook = NATIVE[NATIVE.index("void __fastcall HookPauseGame"):NATIVE.index("bool InstallPauseBarrierHook")]\n        self.assertIn("framework == g_gameFramework", hook)\n        self.assertIn("g_pendingPauseAttempt.load", hook)\n        self.assertLess(hook.index("g_originalPauseGame("), hook.index("g_pauseBarrierObserved.store(true"))\n        self.assertEqual(NATIVE.count("g_originalPauseGame("), 1)\n''',
    '''    def test_pause_hook_keeps_vanilla_pause_ownership_and_zeroes_only_clean_pause_audio_fade(self):\n        hook = NATIVE[NATIVE.index("void __fastcall HookPauseGame"):NATIVE.index("bool InstallPauseBarrierHook")]\n        self.assertIn("framework == g_gameFramework", hook)\n        self.assertIn("g_pendingPauseAttempt.load", hook)\n        self.assertIn("const unsigned int effectiveFadeOutInMs = observe ? 0u : fadeOutInMs;", hook)\n        self.assertIn("g_originalPauseGame(framework, pause, force, effectiveFadeOutInMs);", hook)\n        self.assertNotIn("g_originalPauseGame(framework, pause, force, fadeOutInMs);", hook)\n        self.assertIn("requestedFadeMs=%u effectiveFadeMs=%u", hook)\n        self.assertLess(hook.index("g_originalPauseGame("), hook.index("g_pauseBarrierObserved.store(true"))\n        self.assertEqual(NATIVE.count("g_originalPauseGame("), 1)\n''',
)

replace_once(
    "tools/validate_native_contract.py",
    '''if "g_originalPauseGame(framework, pause, force, fadeOutInMs);" not in pause_hook:\n    raise SystemExit("PauseGame observer must forward vanilla arguments unchanged")\n''',
    '''if "const unsigned int effectiveFadeOutInMs = observe ? 0u : fadeOutInMs;" not in pause_hook:\n    raise SystemExit("pending Clean Pause must clamp only the documented SFX/Voice fade duration")\nif "g_originalPauseGame(framework, pause, force, effectiveFadeOutInMs);" not in pause_hook:\n    raise SystemExit("PauseGame hook must preserve vanilla pause/force ownership and use only the scoped audio fade override")\nif "requestedFadeMs=%u effectiveFadeMs=%u" not in pause_hook:\n    raise SystemExit("PauseGame log must expose requested and effective audio fade durations")\n''',
)

replace_once(
    "docs/DESIGN.md",
    '''2. observes the validated vanilla `IGameFramework::PauseGame(true, ...)` return as the preferred event barrier; the mod never calls `PauseGame` itself and never changes its arguments;\n3. accepts presentation ownership immediately after the outer physical press dispatch returns when that barrier was observed, instead of waiting for Start/Escape release;\n''',
    '''2. observes the validated vanilla `IGameFramework::PauseGame(true, ...)` call as the preferred event barrier; the mod never calls `PauseGame` itself; for the exact pending Clean Pause transition it preserves vanilla `pause`/`force` ownership but clamps only the documented SFX/Voice fade duration to `0 ms`, so dialogue does not continue after the retained frame freezes;\n3. accepts presentation ownership immediately after the outer physical press dispatch returns when that barrier was observed, instead of waiting for Start/Escape release;\n''',
)

replace_once(
    "docs/DESIGN.md",
    '''The mask transaction can begin while pause entry is still pending, before `Menu@0` becomes verifiably visible. The preferred completion point is the return from KCD2's own validated `IGameFramework::PauseGame(true, ...)` call during the forwarded physical press. The detour only records that barrier; Clean Pause presentation is accepted after the outer `PostInputEvent` forwarding returns, avoiding re-entrant Flash/Lua work inside `PauseGame` itself. If no verified barrier is observed, the existing Menu-visibility path remains the compatibility fallback.''',
    '''The mask transaction can begin while pause entry is still pending, before `Menu@0` becomes verifiably visible. The preferred completion point is the return from KCD2's own validated `IGameFramework::PauseGame(true, ...)` call during the forwarded physical press. CryEngine documents the third `PauseGame` argument as the SFX/Voice fade-out time; only for this already-validated pending Clean Pause call the detour changes that duration to `0 ms`, while forwarding the original `pause` and `force` values unchanged. This removes the otherwise intentional audio tail after the visual frame has frozen. The detour records the barrier after vanilla returns; Clean Pause presentation is accepted after the outer `PostInputEvent` forwarding returns, avoiding re-entrant Flash/Lua work inside `PauseGame` itself. If no verified barrier is observed, the existing Menu-visibility path remains the compatibility fallback.''',
)

replace_once(
    "docs/DESIGN.md",
    '''IGameFramework::PauseGame            -> slot 13 (observer only)\n''',
    '''IGameFramework::PauseGame            -> slot 13 (vanilla owner; pending Clean Pause audio fade -> 0 ms)\n''',
)

replace_once(
    "CHANGELOG.md",
    '''- Prevents KCD2's pause HUD-mask transition from rendering an intermediate hidden-HUD frame before Clean Pause presentation is established.\n''',
    '''- Prevents KCD2's pause HUD-mask transition from rendering an intermediate hidden-HUD frame before Clean Pause presentation is established.\n- Synchronizes Clean Pause audio with the retained frame by clamping only the pending Clean Pause `PauseGame` SFX/Voice fade duration to `0 ms`; KCD2 still owns the actual pause and the original `pause`/`force` values.\n''',
)

Path(__file__).unlink()
print("PR34 zero-audio-fade correction applied")
