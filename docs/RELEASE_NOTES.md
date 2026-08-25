# KCD2 Clean Pause v0.1.1-rc.4

Prerelease for **Kingdom Come: Deliverance II 1.5.6** on Windows. KCD2 still owns the real pause lifecycle. This revision extends subtitle preservation to active NPC speech bubbles / overhead subtitles while retaining the blur-free Clean Pause presentation introduced in rc.3.

## Two installation editions

This release publishes two mutually exclusive packages built from the same Clean Pause runtime:

- `kcd2-clean-pause-v0.1.1-rc.4-asi.zip` — contains `KCD2CleanPause.asi`; requires a compatible x64 ASI loader, normally installed as `dinput8.dll` beside the game executable / `WHGame.dll`.
- `kcd2-clean-pause-v0.1.1-rc.4-version-dll.zip` — contains the standalone `version.dll` proxy; no separate ASI loader is required.

Use the ASI edition when another mod already owns `version.dll` or when you already use a shared ASI loader. Do **not** install both Clean Pause editions together. A process-wide guard prevents duplicate native hooks if both editions are accidentally present, but dual installation is not a supported configuration.

## What it does

- Escape / Xbox Start enters a real vanilla-owned pause without drawing the ordinary pause menu.
- World simulation and audio pause through KCD2's own pause lifecycle.
- Gameplay HUD child presentation is restored so visible dialogue subtitles remain on screen while Clean Pause is active.
- Active NPC speech bubbles / overhead subtitles are preserved across the pause transition instead of disappearing when vanilla pause updates the bubble system.
- The retained frame is kept sharp: `wh_cl_NearDof` and `r_DepthOfField` are temporarily set to `0` only while Clean Pause owns hidden-menu presentation.
- The exact previous DoF values are captured with CryEngine's `System.GetCVar` Lua API and restored before Escape/Start or Xbox B reveals the already-open vanilla pause menu.
- Escape / Start again reveals the already-open vanilla pause menu without an intermediate gameplay tick.
- Xbox B from Clean Pause also reveals the vanilla pause menu.
- Failure paths prefer the visible vanilla pause menu instead of trapping input.

## Overhead-subtitle preservation

KCD2's `Bubbles` root HUD clip is not the complete state of overhead chatter. `C_UIHudBubbles` owns separate bubble IDs and Flash objects, and vanilla pause can update/release those objects even if the root `Bubbles` clip is restored.

rc.4 discovers `C_UIHudBubbles` from the live `hud@0` event-listener storage using MSVC RTTI. It then freezes only `I_UIHudBubbles::UpdateBubbles()` and `ReleaseBubble()` while `Menu@0` is logically visible. The freeze is armed before vanilla `Menu@0::SetVisible(true)` runs and is released only after `SetVisible(false)` returns, allowing the first post-pause bubble update to reconcile genuinely stale lines.

No storefront-specific `WHGame.dll` address is used. Bubble discovery is optional/fail-open: if the concrete listener layout cannot be validated, the normal Clean Pause mechanism continues unchanged rather than refusing to pause.

## Retail acceptance evidence

- The core KCD2-owned pause/HUD mechanism is retail-proven on the primary Xbox Store KCD2 1.5.6 target.
- rc.3 is retail-confirmed to enter Clean Pause and remove the visible pause DoF blur.
- rc.4 is retail-confirmed to preserve NPC overhead subtitles in Clean Pause: the overhead lines appear together with the restored main HUD instead of disappearing on pause.
- Exact DoF restoration on the subsequent visible-menu/gameplay handoff remains an explicit stable-release acceptance check.
- A longer post-resume observation remains useful to confirm that an old overhead line cannot become permanently stuck after KCD2 regains bubble ownership.

## Known behavior / acceptance status

- **B does not resume directly from Clean Pause.** It reveals the normal KCD2 pause menu; resume from there normally.
- Runtime compatibility is currently claimed for KCD2 1.5.6 only.
- The standalone `version.dll` loading path is already retail-proven on the primary Xbox Store target.
- The ASI loading path still requires its dedicated retail-equivalence checklist and shared-loader coexistence check.

## Safety/implementation notes

The implementation intentionally avoids custom/inferred PauseGame calls, action-map replacement, Menu visibility mutation, fixed storefront-specific WHGame RVAs, long-lived Flash movieclip pointers, destructive `Release()` calls on `IUIElement::GetMovieClip()` results, and synthetic B-resume replay.

The DoF change is never persisted to configuration. The overhead-bubble preservation does not reconstruct text or anchors; it keeps KCD2's existing bubble objects alive across the pause lifecycle and returns ownership to KCD2 when the menu actually closes.
