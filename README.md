# KCD2 Clean Pause

Clean Pause for **Kingdom Come: Deliverance II** on Windows.

Tested target: **KCD2 1.5.6**, primarily the PC Xbox Store / Xbox app / Game Pass build with an Xbox controller.

## Behavior

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  Escape / Xbox Start -> visible vanilla pause menu
  Xbox B               -> visible vanilla pause menu

Vanilla pause menu
  normal KCD2 controls -> resume / settings / save / quit
```

Clean Pause uses KCD2's own pause lifecycle. World simulation and audio pause as they do in the normal game pause, while the pause-menu surface itself is not drawn. The mod restores the gameplay HUD child state so subtitles that were visible at pause entry remain visible.

The strong depth-of-field blur applied by the vanilla pause is intentionally left unchanged.

### Known v0.1.0 behavior

Xbox **B does not resume directly from Clean Pause**. It reveals the ordinary KCD2 pause menu; use the normal menu controls to resume. This is an accepted v0.1.0 behavior, not a release blocker.

## Install

1. Close KCD2.
2. Remove/disable any older Clean Pause PAK under `Documents\kingdomcome_mods\clean_pause`.
3. Download `kcd2-clean-pause-v0.1.0.zip` from GitHub Releases.
4. Place `version.dll` beside the KCD2 executable / `WHGame.dll`.
5. Start the game normally.

Do **not** overwrite another mod's unrelated `version.dll`. If another mod already owns that proxy DLL, the two need an explicit compatibility solution.

The mod writes `kcd2_clean_pause_native.log` beside `version.dll`.

## Uninstall

Close KCD2 and remove only this mod's `version.dll` and optional `kcd2_clean_pause_native.log`.

## Architecture

The native implementation:

- forwards the real Escape/Start event to vanilla KCD2;
- uses `Menu@0::IsVisible()` as the retail-proven pause lifecycle signal;
- keeps `Menu@0` logically visible and suppresses only its `Render()` call during Clean Pause;
- snapshots the visibility of KCD2's 28 HUD child movie clips before pause and restores that gameplay presentation while Clean Pause is active;
- treats `IUIElement::GetMovieClip()` results as borrowed, call-local handles: never retained, never `Release()`d by the mod;
- suppresses only the HUD Flash calls `ClearSubtitles` and `HideNarrativeSubtitles` while Clean Pause owns presentation;
- fails open to the visible vanilla pause menu when an assumption cannot be verified.

No custom/inferred `PauseGame`, action-map replacement, fixed storefront-specific WHGame RVA, or replacement overlay is used.

## Documentation

- [Current status](docs/STATUS_AND_PLAN.md)
- [Design](docs/DESIGN.md)
- [Testing](docs/TESTING.md)
- [Release process](docs/RELEASE.md)
- [Rejected hypotheses and evidence](docs/REJECTED_HYPOTHESES.md)
- [Latest retail evidence](docs/RETAIL_EVIDENCE_RC7G.md)
