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

While Clean Pause owns presentation, KCD2 depth-of-field is temporarily disabled so the retained game frame remains sharp. The mod snapshots the current `wh_cl_NearDof` and `r_DepthOfField` values and restores them before returning presentation to the visible vanilla pause menu. Ordinary gameplay and the visible vanilla pause menu therefore keep the user's existing graphics settings.

### Known v0.1.0 behavior

Xbox **B does not resume directly from Clean Pause**. It reveals the ordinary KCD2 pause menu; use the normal menu controls to resume. This is an accepted v0.1.0 behavior, not a release blocker.

## Editions

Every new release publishes two mutually exclusive editions built from the same Clean Pause runtime:

- **ASI edition** — `KCD2CleanPause.asi`; recommended when you already use an ASI loader or another mod owns `version.dll`.
- **Standalone edition** — `version.dll`; no separate ASI loader is required, but it conflicts with any unrelated mod that also installs `version.dll` beside the game executable.

Do **not** install both Clean Pause editions at the same time. A process-wide safety guard also prevents a second Clean Pause edition from installing duplicate native hooks if both files are accidentally present.

See [Dual native packages](docs/DUAL_PACKAGE.md) for the packaging contract and [ASI retail acceptance](docs/ASI_RETAIL_ACCEPTANCE.md) for the additional acceptance gate of the new loader path.

## Install — ASI edition

1. Close KCD2.
2. Remove/disable any older Clean Pause installation, including the standalone Clean Pause `version.dll`.
3. Install a compatible x64 ASI loader for KCD2, normally as `dinput8.dll` beside the KCD2 executable / `WHGame.dll`.
4. Copy `KCD2CleanPause.asi` from the `-asi.zip` release asset beside the loader.
5. Start the game normally.

Do not overwrite an existing `dinput8.dll` blindly. Multiple ASI plugins should share one compatible loader installation.

## Install — standalone version.dll edition

1. Close KCD2.
2. Remove/disable any older Clean Pause installation, including `KCD2CleanPause.asi`.
3. Copy `version.dll` from the `-version-dll.zip` release asset beside the KCD2 executable / `WHGame.dll`.
4. Start the game normally.

Do **not** overwrite another mod's unrelated `version.dll`. If another mod already owns that proxy DLL, use the ASI edition instead when possible.

Both editions write `kcd2_clean_pause_native.log` beside their own native module.

## Uninstall

Close KCD2 and remove only the installed Clean Pause edition plus the optional `kcd2_clean_pause_native.log`.

For the ASI edition, remove `dinput8.dll` only if no other installed mod needs that ASI loader.

## Architecture

Both release editions use the same native Clean Pause runtime. They differ only in bootstrap:

- the ASI edition is loaded by a shared ASI loader and calls `clean_pause::Start()` from its own `DllMain`;
- the standalone edition remains a Windows `version.dll` proxy and calls the same `clean_pause::Start()` runtime.

The runtime:

- forwards the real Escape/Start event to vanilla KCD2;
- uses `Menu@0::IsVisible()` as the retail-proven pause lifecycle signal;
- keeps `Menu@0` logically visible and suppresses only its `Render()` call during Clean Pause;
- snapshots the visibility of KCD2's 28 HUD child movie clips before pause and restores that gameplay presentation while Clean Pause is active;
- treats `IUIElement::GetMovieClip()` results as borrowed, call-local handles: never retained, never `Release()`d by the mod;
- suppresses only the HUD Flash calls `ClearSubtitles` and `HideNarrativeSubtitles` while Clean Pause owns presentation;
- temporarily sets `wh_cl_NearDof` and `r_DepthOfField` to `0` only for Clean Pause, restoring their exact previous values before normal presentation resumes;
- fails open to the visible vanilla pause menu when an assumption cannot be verified.

No custom/inferred `PauseGame`, action-map replacement, fixed storefront-specific WHGame RVA, or replacement overlay is used.

## Documentation

- [Current status](docs/STATUS_AND_PLAN.md)
- [Design](docs/DESIGN.md)
- [Dual native packages](docs/DUAL_PACKAGE.md)
- [ASI retail acceptance](docs/ASI_RETAIL_ACCEPTANCE.md)
- [Testing](docs/TESTING.md)
- [Release process](docs/RELEASE.md)
- [Rejected hypotheses and evidence](docs/REJECTED_HYPOTHESES.md)
- [Latest retail evidence](docs/RETAIL_EVIDENCE_RC7G.md)
