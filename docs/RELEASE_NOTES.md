# KCD2 Clean Pause v0.1.1-rc.3

Prerelease for **Kingdom Come: Deliverance II 1.5.6** on Windows. KCD2 still owns the real pause lifecycle; this revision corrects the Lua CVar getter used by the blur-free presentation path and retains the dual native packaging introduced in rc.1.

## Two installation editions

This release publishes two mutually exclusive packages built from the same Clean Pause runtime:

- `kcd2-clean-pause-v0.1.1-rc.3-asi.zip` — contains `KCD2CleanPause.asi`; requires a compatible x64 ASI loader, normally installed as `dinput8.dll` beside the game executable / `WHGame.dll`.
- `kcd2-clean-pause-v0.1.1-rc.3-version-dll.zip` — contains the standalone `version.dll` proxy; no separate ASI loader is required.

Use the ASI edition when another mod already owns `version.dll` or when you already use a shared ASI loader. Do **not** install both Clean Pause editions together. A process-wide guard prevents duplicate native hooks if both editions are accidentally present, but dual installation is not a supported configuration.

## What it does

- Escape / Xbox Start enters a real vanilla-owned pause without drawing the ordinary pause menu.
- World simulation and audio pause through KCD2's own pause lifecycle.
- Gameplay HUD child presentation is restored so visible subtitles can remain on screen while Clean Pause is active.
- The retained frame is kept sharp: `wh_cl_NearDof` and `r_DepthOfField` are temporarily set to `0` only while Clean Pause owns hidden-menu presentation.
- The exact previous DoF values are captured with CryEngine's `System.GetCVar` Lua API and restored before Escape/Start or Xbox B reveals the already-open vanilla pause menu.
- The same DoF restoration is attempted on fail-open paths; inability to capture/disable DoF safely prevents Clean Pause from taking presentation ownership.
- Escape / Start again reveals the already-open vanilla pause menu without an intermediate gameplay tick.
- Xbox B from Clean Pause also reveals the vanilla pause menu.
- Failure paths prefer the visible vanilla pause menu instead of trapping input.

## Retail acceptance evidence

rc.2 must not be used for testing. It called a nonexistent `System.GetCVarValue` function, so the DoF controller always failed its capability check and Clean Pause fell back to the ordinary visible pause menu.

rc.3 corrects that call to `System.GetCVar`. On the primary Xbox Store KCD2 1.5.6 target, a retail test confirmed that Xbox Start enters Clean Pause again and the retained frame is sharp with the pause DoF blur removed.

That confirmation covers the corrected blur-entry path. The subsequent visible-menu/gameplay DoF restoration handoff still needs an explicit retail observation before stable promotion.

## Known behavior / acceptance status

- **B does not resume directly from Clean Pause.** It reveals the normal KCD2 pause menu; resume from there normally.
- Runtime compatibility is currently claimed for KCD2 1.5.6 only.
- The standalone `version.dll` loading path is already retail-proven on the primary Xbox Store target.
- The corrected rc.3 blur-entry path is retail-confirmed.
- The ASI loading path still requires its dedicated retail-equivalence checklist and shared-loader coexistence check.
- Exact DoF restoration before visible-menu/gameplay presentation still needs explicit retail confirmation.

## Safety/implementation notes

The implementation intentionally avoids custom/inferred PauseGame calls, action-map replacement, Menu visibility mutation, fixed storefront-specific WHGame RVAs, long-lived Flash movieclip pointers, destructive `Release()` calls on `IUIElement::GetMovieClip()` results, and synthetic B-resume replay.

The DoF change is not a user preference and is never persisted to configuration: it is a bounded presentation override active only during Clean Pause.
