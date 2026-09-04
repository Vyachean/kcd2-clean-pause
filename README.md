# KCD2 Clean Pause

Clean Pause for **Kingdom Come: Deliverance II** on Windows.

The current stable release, **v0.2.2**, was runtime-tested with **KCD2 1.5.6 on the PC Xbox Store / Xbox app version**, using an Xbox controller.

The current published GitHub prerelease, **v0.3.0-rc.4**, introduced fail-closed KCD2 1.5.6 compatibility profiles for **Steam, GOG, Epic Games Store, and Xbox / Microsoft Store**. The source on `main` contains the later Steam acceptance fixes from PR #51; those changes have not been promoted to a new public native release because Defender / Smart App Control investigation #38 is still a release blocker.

Steam 1.5.6 `release_1_5-15693` is now runtime-accepted on the current source. The accepted path uses the exact Steam build fingerprint, canonical `gEnv`, the real `CCryAction` `IGameFramework` singleton, visible-menu gesture passthrough, and authoritative `C_UIHudMask` state for the fast gameplay HUD snapshot. GOG/Epic profiles are backed by distribution-specific reverse-engineering/runtime evidence but are not yet claimed as Clean Pause runtime-tested by this project.

## Release status

- **Current stable release:** v0.2.2.
- **Current published GitHub prerelease:** v0.3.0-rc.4.
- **Current source runtime acceptance:** Xbox / Microsoft Store 1.5.6 baseline plus Steam 1.5.6 `release_1_5-15693` acceptance on `main`.
- **GOG / Epic Games Store:** compatibility profiles implemented; Clean Pause-specific smoke QA still pending.
- **Published edition:** KCD2CleanPause.asi, using the upstream Ultimate ASI Loader.
- **Standalone version.dll:** built and validated, but new publication remains withheld.
- **Stable v0.3.0:** blocked by Defender / Smart App Control issue #38. The final `main` ASI is also detected by current ML/heuristic scanners, so the accepted runtime is not being promoted until that investigation is resolved.

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

- Xbox **B does not resume directly from Clean Pause**. It reveals the ordinary KCD2 pause menu; use the normal menu controls to resume.
- The current Steam acceptance build can still show a single residual visual frame when the retained gameplay HUD becomes visible after the game is already paused. This is non-blocking and tracked in #52.

## Editions

Both native targets compile the same Clean Pause runtime and remain mutually exclusive installations.

- **ASI edition — public distribution:** KCD2CleanPause.asi, packaged with the pinned official x64 Ultimate ASI Loader dinput8.dll for fresh installation.
- **Standalone edition — built and validated, but new builds are not distributed:** version.dll; public distribution remains blocked by #38.

Do **not** intentionally install both Clean Pause editions at the same time. A process-wide guard prevents duplicate hooks if both are accidentally loaded, but dual installation is unsupported.

Native hooks are **process-lifetime state**. Hot unload/reload of KCD2CleanPause.asi or version.dll is not supported; close KCD2 before replacing or removing the native module.

See [Dual native packages](docs/DUAL_PACKAGE.md) for the package contract.

## Install — ASI edition

### Fresh installation

1. Close KCD2.
2. Remove any standalone Clean Pause version.dll installation.
3. Open the directory containing the KCD2 executable / WHGame.dll.
4. Copy both dinput8.dll and KCD2CleanPause.asi from the release ZIP into that same directory.
5. Start the game normally.

### Existing ASI loader

If another mod already installed a compatible dinput8.dll, **do not overwrite it blindly**.

KCD2CleanPause.asi must be placed where that existing ASI loader actually searches for plugins. With Ultimate ASI Loader, the simplest shared-loader layout is to place KCD2CleanPause.asi beside the existing dinput8.dll. Ultimate ASI Loader can also load plugins from its scripts/ and plugins/ directories.

Do not leave dinput8.dll in one directory and place KCD2CleanPause.asi beside WHGame.dll in another directory unless that loader is explicitly configured to scan the latter location.

Multiple ASI plugins may share one compatible loader, but loader location and plugin search paths are part of that loader's configuration.

The package also contains ASI_LOADER_SOURCE.txt and ULTIMATE_ASI_LOADER_LICENSE.txt documenting the exact upstream loader release, provenance, hashes, and MIT license.

## Runtime acceptance

For a candidate built from current source, the core smoke contract is:

1. launch the game and load into gameplay;
2. press Escape / Start and confirm Clean Pause retains the gameplay frame, HUD and applicable subtitles;
3. press Escape / Start again and confirm the ordinary vanilla pause menu appears immediately;
4. on controller, B from Clean Pause reveals the same vanilla pause menu;
5. resume normally and confirm gameplay continues;
6. repeat several cycles and include kcd2_clean_pause_native.log with any unexpected result.

Steam acceptance on `main` confirmed the exact Steam 1.5.6 profile and canonical `gEnv`, corrected the old `IGame[16]` framework assumption, and validated the canonical `CCryAction` PauseGame observer. The recurring pre-pause hitch was removed by taking the gameplay snapshot from authoritative `C_UIHudMask` state rather than synchronously walking 28 Flash clips on every pause press.

The Xbox / Microsoft Store path keeps its independently runtime-tested legacy environment/framework adapter. The shared Clean Pause core is common, but the storefront-specific discovery adapters are intentionally not assumed to be identical. A current-source Xbox regression smoke remains appropriate before the next public native release because shared HUD/presentation code has changed since the original stable acceptance.

## Troubleshooting

When Clean Pause is successfully loaded, it creates kcd2_clean_pause_native.log beside KCD2CleanPause.asi.

If **no log is created at all**, first verify that the ASI loader is actually loading KCD2CleanPause.asi from its configured plugin location.

If the game crashes while loading native mods, isolate the loader from the plugin:

1. Keep the ASI loader in the location being tested.
2. Temporarily remove KCD2CleanPause.asi and any other .asi plugins from that loader's search path.
3. Start the game.
4. If the game starts normally, add only KCD2CleanPause.asi and test again.

If the game works with the loader alone but crashes after adding Clean Pause, report it as a Clean Pause compatibility issue and include:

- KCD2 version;
- storefront/build (Steam, GOG, Epic Games Store, Xbox / Microsoft Store, or another build);
- locations of dinput8.dll and KCD2CleanPause.asi;
- kcd2_clean_pause_native.log, if one was created before the crash.

The profiled runtime log records the PE fingerprint, detected storefront/build metadata, selected ABI/profile, environment-validation strategy and whether the profile reached hook installation.

## Standalone version.dll edition

The project still builds and validates the standalone proxy, but new standalone builds are not published while #38 is unresolved. Do not obtain or whitelist an unofficial standalone build to work around that release gate.

The immutable v0.2.0 release still contains the older retail-proven standalone package, but it does not contain the later pause-transition fixes.

Both native editions write kcd2_clean_pause_native.log beside their own module.

## Uninstall

Close KCD2 and remove KCD2CleanPause.asi plus the optional kcd2_clean_pause_native.log. Remove dinput8.dll only if no other installed ASI mod needs that loader.

Do not hot-unload the native module from a running game. Clean Pause deliberately keeps its MinHook detours and runtime identities for the lifetime of the KCD2 process.

## Architecture

The production architecture deliberately keeps KCD2 as the sole pause owner:

- the physical Escape/Start event is forwarded to KCD2;
- a validated IGameFramework::PauseGame(true, ...) hook can observe the real vanilla pause transition but never synthesizes a pause and forwards the original arguments unchanged;
- the PauseGame observer is an optional capability: failure to resolve it does not block the PostInputEvent/Menu fallback;
- the shared Clean Pause state/presentation core is used by all supported profiles;
- storefront, build identity, ABI, environment discovery and optional engine capabilities are modeled separately;
- Steam 1.5.6 resolves IGameFramework from the documented CCryAction singleton instead of interpreting IGame[16] as framework, and acquires the optional observer lazily on validated Pause input;
- Xbox / Microsoft Store 1.5.6 keeps its separately proven legacy environment/framework adapter instead of exporting that assumption to other storefronts;
- known distribution-specific canonical gEnv/framework RVAs are used only behind the matching exact build profile and strong live identity checks;
- pending Start/release correlation alone performs no HUD replay;
- HUD/subtitle preservation is armed only for the real vanilla pause transition when the barrier is available, with Menu visibility providing the compatibility fallback;
- Menu@0 remains logically visible while only its Render() is suppressed during Clean Pause;
- authoritative C_UIHudMask visibility is retained for safe vanilla-menu handoff/fail-open and for the fast gameplay snapshot;
- exact root HUD visibility, dialogue subtitles, NPC overhead subtitles and DoF state are preserved;
- unknown or mismatched builds install no version-specific Clean Pause hooks.

No action-map replacement, replacement overlay, long-lived movieclip pointer, destructive borrowed-handle release, synthetic B-resume replay, or unguarded cross-store binary assumption is used.

The translation-unit wrapper tracked in #45 has been removed in this refactor: production compiles `clean_pause_native.cpp` directly, with no macro bootstrap substitution and no textual `.cpp` inclusion. The remaining #45 work is a behavior-preserving private boundary between storefront/build bootstrap adapters and the shared Clean Pause state/presentation core; that deeper structural split remains gated on focused Steam and Xbox regression smoke.

See [Runtime compatibility](docs/RUNTIME_COMPATIBILITY.md) and [Design](docs/DESIGN.md) for the complete production architecture.

## Versioning

The project follows SemVer and immutable tag-backed GitHub releases. Feature releases bump MINOR, fixes bump PATCH, and release candidates are used only when the supported release itself still needs acceptance. See [Release process](docs/RELEASE.md).

## Documentation

Start with the [documentation index](docs/README.md).

Key current documents:

- [Current status and release readiness](docs/STATUS_AND_PLAN.md)
- [Runtime compatibility](docs/RUNTIME_COMPATIBILITY.md)
- [Nexus Mods publication copy](docs/NEXUS.md)
- [Design](docs/DESIGN.md)
- [Testing](docs/TESTING.md)
- [Release process](docs/RELEASE.md)
