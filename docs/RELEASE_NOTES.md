# KCD2 Clean Pause v0.1.0

Initial stable release for **Kingdom Come: Deliverance II 1.5.6** on Windows, with primary retail testing on the PC Xbox Store / Xbox app build.

## What it does

- Escape / Xbox Start enters a real vanilla-owned pause without drawing the ordinary pause menu.
- World simulation and audio pause through KCD2's own pause lifecycle.
- Gameplay HUD child presentation is restored so visible subtitles can remain on screen while Clean Pause is active.
- Escape / Start again reveals the already-open vanilla pause menu without an intermediate gameplay tick.
- Xbox B from Clean Pause also reveals the vanilla pause menu.
- Failure paths prefer the visible vanilla pause menu instead of trapping input.

## Known behavior

- **B does not resume directly from Clean Pause in v0.1.0.** It reveals the normal KCD2 pause menu; resume from there normally.
- KCD2's vanilla pause depth-of-field blur remains visible and is intentionally not modified.
- Compatibility is currently claimed for KCD2 1.5.6 only.

## Safety/implementation notes

The stable implementation intentionally does not ship the experimental synthetic B-resume replay route. It also avoids custom/inferred PauseGame calls, action-map replacement, Menu visibility mutation, fixed storefront-specific WHGame RVAs, long-lived Flash movieclip pointers, and destructive `Release()` calls on `IUIElement::GetMovieClip()` results.
