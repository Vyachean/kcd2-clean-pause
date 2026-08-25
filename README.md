# KCD2 Clean Pause

Clean Pause for **Kingdom Come: Deliverance II** on Windows.

Tested target: **KCD2 1.5.6**, primarily the PC Xbox Store / Xbox app / Game Pass build with an Xbox controller.

## Release status

- **Current stable target:** `v0.2.0`.
- **Retail-supported edition:** standalone `version.dll`.
- **ASI edition:** experimental until someone completes a retail loader/coexistence check.

`v0.2.0` adds duplicate-load protection, blur-free Clean Pause presentation, and preservation of NPC overhead subtitles. The standalone path has been exercised in retail and normal pause/menu/resume behavior is accepted. The ASI package uses the same runtime but a different loader path and is therefore shipped as an unverified alternative rather than blocking the stable standalone release.

Use the GitHub Releases page as the source of truth for versions that are actually published.

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

Clean Pause uses KCD2's own pause lifecycle. World simulation and audio pause as they do in the normal game pause, while the pause-menu surface itself is not drawn. The mod restores the gameplay HUD state so subtitles that were visible at pause entry remain visible.

In `v0.2.0`, Clean Pause also removes the vanilla pause depth-of-field blur while hidden-menu presentation is active and preserves active NPC overhead speech bubbles. The previous `wh_cl_NearDof` and `r_DepthOfField` values are captured and restored before ordinary visible vanilla presentation resumes.

### Known behavior

Xbox **B does not resume directly from Clean Pause**. It reveals the ordinary KCD2 pause menu; use the normal menu controls to resume. This is the accepted product contract.

Compatibility is currently claimed for **KCD2 1.5.6 only**. A game update requires ABI revalidation before support is claimed.

## Editions

`v0.2.0` publishes two mutually exclusive packages built from the same runtime:

- **Standalone edition — supported:** `version.dll`; no separate ASI loader is required.
- **ASI edition — experimental:** `KCD2CleanPause.asi`; intended for users who already have a compatible ASI loader or another mod owns `version.dll`.

Do **not** intentionally install both Clean Pause editions at the same time. A process-wide guard prevents duplicate Clean Pause hooks if both editions are accidentally loaded, but dual installation is unsupported.

See [Dual native packages](docs/DUAL_PACKAGE.md) for the package contract and [ASI retail acceptance](docs/ASI_RETAIL_ACCEPTANCE.md) for the checks still missing for the ASI loading path.

## Install — standalone version.dll edition

1. Close KCD2.
2. Remove/disable any older Clean Pause ASI installation.
3. Copy `version.dll` from the `-version-dll.zip` release asset beside the KCD2 executable / `WHGame.dll`.
4. Start the game normally.

Do **not** overwrite another mod's unrelated `version.dll`. If another mod already owns that proxy DLL, the ASI edition is available as an experimental alternative.

## Install — ASI edition (experimental)

1. Close KCD2.
2. Remove the standalone Clean Pause `version.dll`.
3. Install a compatible x64 ASI loader for KCD2, normally as `dinput8.dll` beside the KCD2 executable / `WHGame.dll`.
4. Copy `KCD2CleanPause.asi` from the `-asi.zip` release asset beside the loader.
5. Start the game normally.

Do not overwrite an existing `dinput8.dll` blindly. Multiple ASI plugins should share one compatible loader installation.

Both native editions write `kcd2_clean_pause_native.log` beside their own module.

## Uninstall

Close KCD2 and remove only the installed Clean Pause edition plus the optional `kcd2_clean_pause_native.log`.

For the ASI edition, remove `dinput8.dll` only if no other installed mod needs that ASI loader.

## Architecture

The current production architecture deliberately keeps KCD2 as the sole pause owner:

- the real Escape/Start event is forwarded to KCD2;
- `Menu@0::IsVisible()` is used as the pause-lifecycle signal;
- `Menu@0` remains logically visible while only its `Render()` is suppressed during Clean Pause;
- gameplay HUD child visibility is restored from boolean snapshots;
- subtitle-clearing Flash calls are narrowly suppressed while Clean Pause owns presentation;
- active NPC overhead subtitles are preserved separately;
- pause DoF blur is temporarily removed and the prior values are restored before normal vanilla presentation;
- unresolved core state fails open to the visible vanilla pause menu.

No custom/inferred `PauseGame`, action-map replacement, fixed storefront-specific `WHGame.dll` RVA, replacement overlay, long-lived movieclip pointer, or synthetic B-resume replay is used.

See [Design](docs/DESIGN.md) for the complete production architecture.

## Versioning

The project follows SemVer and a tag-driven GitHub release flow. Feature releases bump MINOR, fixes bump PATCH, and release candidates are used only when the supported release itself still needs acceptance. See [Release process](docs/RELEASE.md).

## Documentation

Start with the [documentation index](docs/README.md).

Key current documents:

- [Current status and release readiness](docs/STATUS_AND_PLAN.md)
- [Design](docs/DESIGN.md)
- [Testing](docs/TESTING.md)
- [Release process](docs/RELEASE.md)
