# KCD2 Clean Pause

Clean Pause for **Kingdom Come: Deliverance II** on Windows.

Tested target: **KCD2 1.5.6**, primarily the PC Xbox Store / Xbox app / Game Pass build with an Xbox controller.

## Release status

- **Latest stable:** `v0.1.0`.
- **Current development target:** `v0.2.0-rc.1` on `main`.

`v0.1.0` is the original standalone `version.dll` release. The `0.2.0` feature line adds the ASI edition, duplicate-load protection, blur-free Clean Pause presentation, and preservation of NPC overhead subtitles. Use the GitHub Releases page as the source of truth for versions that are actually published.

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

In the `0.2.0` feature line, Clean Pause also removes the vanilla pause depth-of-field blur while hidden-menu presentation is active and preserves active NPC overhead speech bubbles. The previous `wh_cl_NearDof` and `r_DepthOfField` values are captured and restored before ordinary visible vanilla presentation resumes.

### Known behavior

Xbox **B does not resume directly from Clean Pause**. It reveals the ordinary KCD2 pause menu; use the normal menu controls to resume. This is the accepted product contract.

Compatibility is currently claimed for **KCD2 1.5.6 only**. A game update requires ABI revalidation before support is claimed.

## Editions

### v0.1.0 stable

The initial stable release ships one package containing the standalone `version.dll` edition. Follow the standalone installation instructions below.

### v0.2.0 feature line

Starting with the `0.2.0` release line, releases publish two mutually exclusive editions built from the same Clean Pause runtime:

- **ASI edition** — `KCD2CleanPause.asi`; use it when you already have a compatible ASI loader or another mod owns `version.dll`.
- **Standalone edition** — `version.dll`; no separate ASI loader is required, but it conflicts with any unrelated mod that also installs `version.dll` beside the game executable.

Do **not** intentionally install both Clean Pause editions at the same time. A process-wide guard prevents duplicate Clean Pause hooks if both editions are accidentally loaded, but dual installation is unsupported.

See [Dual native packages](docs/DUAL_PACKAGE.md) for the package contract and [ASI retail acceptance](docs/ASI_RETAIL_ACCEPTANCE.md) for the additional acceptance gate of the ASI loading path.

## Install — ASI edition

Applies to `0.2.0`-line releases that provide `KCD2CleanPause.asi`.

1. Close KCD2.
2. Remove/disable any older Clean Pause installation, including the standalone Clean Pause `version.dll`.
3. Install a compatible x64 ASI loader for KCD2, normally as `dinput8.dll` beside the KCD2 executable / `WHGame.dll`.
4. Copy `KCD2CleanPause.asi` from the `-asi.zip` release asset beside the loader.
5. Start the game normally.

Do not overwrite an existing `dinput8.dll` blindly. Multiple ASI plugins should share one compatible loader installation.

## Install — standalone version.dll edition

1. Close KCD2.
2. Remove/disable any older Clean Pause ASI installation.
3. Copy the release `version.dll` beside the KCD2 executable / `WHGame.dll`.
4. Start the game normally.

For `v0.1.0`, `version.dll` is inside the single `kcd2-clean-pause-v0.1.0.zip` asset. For `0.2.0`-line releases, it is inside the `-version-dll.zip` asset.

Do **not** overwrite another mod's unrelated `version.dll`. If another mod already owns that proxy DLL, use the ASI edition from the `0.2.0` feature line when possible.

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
- the `0.2.0` feature line separately preserves active NPC overhead subtitles and temporarily removes pause DoF blur;
- unresolved core state fails open to the visible vanilla pause menu.

No custom/inferred `PauseGame`, action-map replacement, fixed storefront-specific `WHGame.dll` RVA, replacement overlay, long-lived movieclip pointer, or synthetic B-resume replay is used.

See [Design](docs/DESIGN.md) for the complete production architecture.

## Versioning

The project follows SemVer and a tag-driven GitHub release flow. Feature releases bump MINOR, fixes bump PATCH, release candidates use `-rc.N`, and merging to `main` does not itself publish a GitHub Release. See [Release process](docs/RELEASE.md).

## Documentation

Start with the [documentation index](docs/README.md).

Key current documents:

- [Current status and release readiness](docs/STATUS_AND_PLAN.md)
- [Design](docs/DESIGN.md)
- [Testing](docs/TESTING.md)
- [Release process](docs/RELEASE.md)
