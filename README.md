# KCD2 Clean Pause

Clean Pause for **Kingdom Come: Deliverance II** on Windows.

Tested target: **KCD2 1.5.6**, primarily the PC Xbox Store / Xbox app / Game Pass build with an Xbox controller.

## Release status

- **Current stable release:** `v0.2.1`.
- **Published v0.2.1 edition:** `KCD2CleanPause.asi`, retail-accepted with the upstream Ultimate ASI Loader.
- **Standalone `version.dll`:** the v0.2.1 target is intentionally withheld while Defender investigation #38 is unresolved. The last published standalone package is v0.2.0.

`v0.2.1` fixes the remaining pause-entry discontinuity: picture/simulation and ongoing dialogue audio now pause together, while the gameplay HUD/subtitles remain retained without the previous hidden-HUD transition blink.

Use the GitHub Releases page as the source of truth for versions and assets that are actually published.

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

Clean Pause uses KCD2's own pause lifecycle. The vanilla pause menu remains logically open, but its render surface is suppressed while the gameplay presentation is retained. The mod does not manufacture a second pause state.

The current release also removes the vanilla pause depth-of-field blur while Clean Pause is active and preserves normal dialogue subtitles plus active NPC overhead speech bubbles.

### Known behavior

Xbox **B does not resume directly from Clean Pause**. It reveals the ordinary KCD2 pause menu; use the normal menu controls to resume. This is the accepted product contract.

Compatibility is currently claimed for **KCD2 1.5.6 only**. A game update requires ABI revalidation before support is claimed.

## Editions

Both native targets compile the same runtime and remain mutually exclusive installations.

- **ASI edition — current supported v0.2.1 distribution:** `KCD2CleanPause.asi`; requires a compatible x64 ASI loader.
- **Standalone edition — built and validated, but v0.2.1 not distributed:** `version.dll`; public distribution is blocked by Defender investigation #38.

Do **not** intentionally install both Clean Pause editions at the same time. A process-wide guard prevents duplicate hooks if both are accidentally loaded, but dual installation is unsupported.

See [Dual native packages](docs/DUAL_PACKAGE.md) for the package contract.

## Install — ASI edition

1. Close KCD2.
2. Remove any standalone Clean Pause `version.dll` installation.
3. Install a compatible x64 ASI loader for KCD2, normally the upstream Ultimate ASI Loader `dinput8.dll` beside the KCD2 executable / `WHGame.dll`.
4. Copy `KCD2CleanPause.asi` from the `-asi.zip` release asset beside the loader.
5. Start the game normally.

Do not overwrite an existing `dinput8.dll` blindly. Multiple ASI plugins may share one compatible loader, but universal coexistence with every native plugin is not claimed.

## Standalone version.dll edition

The project still builds and validates the standalone proxy, but **v0.2.1 does not publish a standalone asset** while #38 is unresolved. Do not obtain or whitelist an unofficial v0.2.1 `version.dll` build to work around that release gate.

The immutable v0.2.0 release still contains the older retail-proven standalone package, but it does not include the v0.2.1 transition fix.

Both native editions write `kcd2_clean_pause_native.log` beside their own module.

## Uninstall

Close KCD2 and remove `KCD2CleanPause.asi` plus the optional `kcd2_clean_pause_native.log`. Remove the ASI loader `dinput8.dll` only if no other installed mod needs it.

## Architecture

The production architecture deliberately keeps KCD2 as the sole pause owner:

- the physical Escape/Start event is forwarded to KCD2;
- a validated `IGameFramework::PauseGame(true, ...)` hook observes the real vanilla pause transition but never synthesizes a pause and forwards the original arguments unchanged;
- pending Start/release correlation alone performs no HUD replay;
- HUD/subtitle preservation is armed only for the real vanilla pause transition;
- `Menu@0` remains logically visible while only its `Render()` is suppressed during Clean Pause;
- authoritative `C_UIHudMask` visibility is retained for safe vanilla-menu handoff/fail-open;
- exact root HUD visibility, dialogue subtitles, NPC overhead subtitles and DoF state are preserved;
- unresolved core state fails open to the visible vanilla pause menu.

No action-map replacement, fixed storefront-specific `WHGame.dll` RVA, replacement overlay, long-lived movieclip pointer, destructive borrowed-handle release, or synthetic B-resume replay is used.

See [Design](docs/DESIGN.md) for the complete production architecture.

## Versioning

The project follows SemVer and immutable tag-backed GitHub releases. Feature releases bump MINOR, fixes bump PATCH, and release candidates are used only when the supported release itself still needs acceptance. See [Release process](docs/RELEASE.md).

## Documentation

Start with the [documentation index](docs/README.md).

Key current documents:

- [Current status and release readiness](docs/STATUS_AND_PLAN.md)
- [Design](docs/DESIGN.md)
- [Testing](docs/TESTING.md)
- [Release process](docs/RELEASE.md)
