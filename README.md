# KCD2 Clean Pause

Clean Pause for **Kingdom Come: Deliverance II** on Windows.

Tested with **KCD2 1.5.6 on the PC Xbox Store / Xbox app version**, using an Xbox controller.

**Steam compatibility has not yet been explicitly verified.** If you use the Steam version and encounter a crash or the mod does not load, see the troubleshooting notes below and include the native log when available.

## Release status

- **Current stable release:** `v0.2.2`.
- **Published edition:** `KCD2CleanPause.asi`, using the upstream Ultimate ASI Loader.
- The ASI package includes the pinned official x64 Ultimate ASI Loader for a complete fresh installation.
- **Standalone `version.dll`:** new standalone publication remains withheld while Defender investigation #38 is unresolved. The last published standalone package is v0.2.0.

The Clean Pause runtime behavior is unchanged from the retail-accepted v0.2.1 runtime. `v0.2.2` improves distribution and installation by bundling the verified loader with provenance and license information.

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

Clean Pause keeps the retained frame sharp by removing the vanilla pause depth-of-field blur and preserves normal dialogue subtitles plus active NPC overhead speech bubbles.

### Known behavior

Xbox **B does not resume directly from Clean Pause**. It reveals the ordinary KCD2 pause menu; use the normal menu controls to resume.

## Editions

Both native targets compile the same runtime and remain mutually exclusive installations.

- **ASI edition — current public distribution:** `KCD2CleanPause.asi`, packaged with the pinned official x64 Ultimate ASI Loader `dinput8.dll` for fresh installation.
- **Standalone edition — built and validated, but new builds are not distributed:** `version.dll`; public distribution remains blocked by Defender investigation #38.

Do **not** intentionally install both Clean Pause editions at the same time. A process-wide guard prevents duplicate hooks if both are accidentally loaded, but dual installation is unsupported.

See [Dual native packages](docs/DUAL_PACKAGE.md) for the package contract.

## Install — ASI edition

### Fresh installation

1. Close KCD2.
2. Remove any standalone Clean Pause `version.dll` installation.
3. Open the directory containing the KCD2 executable / `WHGame.dll`.
4. Copy both `dinput8.dll` and `KCD2CleanPause.asi` from the release ZIP into that same directory.
5. Start the game normally.

### Existing ASI loader

If another mod already installed a compatible `dinput8.dll`, **do not overwrite it blindly**.

`KCD2CleanPause.asi` must be placed where that existing ASI loader actually searches for plugins. With Ultimate ASI Loader, the simplest shared-loader layout is to place `KCD2CleanPause.asi` beside the existing `dinput8.dll`. Ultimate ASI Loader can also load plugins from its `scripts/` and `plugins/` directories.

Do not leave `dinput8.dll` in one directory and place `KCD2CleanPause.asi` beside `WHGame.dll` in another directory unless that loader is explicitly configured to scan the latter location.

Multiple ASI plugins may share one compatible loader, but loader location and plugin search paths are part of that loader's configuration.

The package also contains `ASI_LOADER_SOURCE.txt` and `ULTIMATE_ASI_LOADER_LICENSE.txt` documenting the exact upstream loader release, provenance, hashes, and MIT license.

## Troubleshooting

When Clean Pause is successfully loaded, it creates `kcd2_clean_pause_native.log` beside `KCD2CleanPause.asi`.

If **no log is created at all**, first verify that the ASI loader is actually loading `KCD2CleanPause.asi` from its configured plugin location.

If the game crashes while loading native mods, isolate the loader from the plugin:

1. Keep the ASI loader in the location being tested.
2. Temporarily remove `KCD2CleanPause.asi` and any other `.asi` plugins from that loader's search path.
3. Start the game.
4. If the game starts normally, add only `KCD2CleanPause.asi` and test again.

If the game works with the loader alone but crashes after adding Clean Pause, report it as a Clean Pause compatibility issue and include:

- KCD2 version;
- storefront/build (Steam, Xbox Store / Xbox app, or other);
- locations of `dinput8.dll` and `KCD2CleanPause.asi`;
- `kcd2_clean_pause_native.log`, if one was created before the crash.

Steam is not yet an explicitly validated runtime target, so Steam reports with the native log are especially useful.

## Standalone version.dll edition

The project still builds and validates the standalone proxy, but new standalone builds are not published while #38 is unresolved. Do not obtain or whitelist an unofficial standalone build to work around that release gate.

The immutable v0.2.0 release still contains the older retail-proven standalone package, but it does not contain the later pause-transition fix.

Both native editions write `kcd2_clean_pause_native.log` beside their own module.

## Uninstall

Close KCD2 and remove `KCD2CleanPause.asi` plus the optional `kcd2_clean_pause_native.log`. Remove `dinput8.dll` only if no other installed ASI mod needs that loader.

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
- [Nexus Mods publication copy](docs/NEXUS.md)
- [Design](docs/DESIGN.md)
- [Testing](docs/TESTING.md)
- [Release process](docs/RELEASE.md)
