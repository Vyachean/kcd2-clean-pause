# KCD2 Clean Pause v0.1.1-rc.1

Prerelease for **Kingdom Come: Deliverance II 1.5.6** on Windows. The Clean Pause runtime is unchanged from the retail-proven v0.1.0 architecture; this release adds a second native loading/package option.

## Two installation editions

This release publishes two mutually exclusive packages built from the same Clean Pause runtime:

- `kcd2-clean-pause-v0.1.1-rc.1-asi.zip` — contains `KCD2CleanPause.asi`; requires a compatible x64 ASI loader, normally installed as `dinput8.dll` beside the game executable / `WHGame.dll`.
- `kcd2-clean-pause-v0.1.1-rc.1-version-dll.zip` — contains the standalone `version.dll` proxy; no separate ASI loader is required.

Use the ASI edition when another mod already owns `version.dll` or when you already use a shared ASI loader. Do **not** install both Clean Pause editions together.

The standalone `version.dll` path retains the v0.1.0 bootstrap and runtime. The ASI edition replaces only the proxy bootstrap with a minimal ASI `DllMain` that starts the same runtime.

## What it does

- Escape / Xbox Start enters a real vanilla-owned pause without drawing the ordinary pause menu.
- World simulation and audio pause through KCD2's own pause lifecycle.
- Gameplay HUD child presentation is restored so visible subtitles can remain on screen while Clean Pause is active.
- Escape / Start again reveals the already-open vanilla pause menu without an intermediate gameplay tick.
- Xbox B from Clean Pause also reveals the vanilla pause menu.
- Failure paths prefer the visible vanilla pause menu instead of trapping input.

## Known behavior

- **B does not resume directly from Clean Pause.** It reveals the normal KCD2 pause menu; resume from there normally.
- KCD2's vanilla pause depth-of-field blur remains visible and is intentionally not modified.
- Runtime compatibility is currently claimed for KCD2 1.5.6 only.
- The standalone `version.dll` loading path is already retail-proven on the primary Xbox Store target. The new ASI loading path remains prerelease until its dedicated retail-equivalence checklist passes.

## Safety/implementation notes

The implementation intentionally avoids custom/inferred PauseGame calls, action-map replacement, Menu visibility mutation, fixed storefront-specific WHGame RVAs, long-lived Flash movieclip pointers, destructive `Release()` calls on `IUIElement::GetMovieClip()` results, and synthetic B-resume replay.
