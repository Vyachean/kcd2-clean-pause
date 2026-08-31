# KCD2 Clean Pause v0.3.0-rc.1

Release candidate for **Kingdom Come: Deliverance II 1.5.6** multi-store compatibility on Windows.

This prerelease is published on GitHub so the new Steam compatibility path can receive a focused in-game smoke test before the runtime is promoted to stable v0.3.0 and the Nexus Mods compatibility claim is expanded.

## What changed

- Adds explicit KCD2 1.5.6 runtime profiles for Steam, GOG, Epic Games Store, and Xbox / Microsoft Store.
- Separates storefront metadata, shipped-build identity, ABI, and environment discovery instead of assuming that all storefronts use the same WHGame.dll binary.
- Fixes the Steam v0.2.2 failure where the old writable-memory gEnv scanner could accept a false-positive object and then read invalid framework/input/UI state.
- Uses exact distribution-specific canonical gEnv evidence for Steam/GOG/Epic; the captured Steam profile additionally performs a one-time independent code-anchor cross-check.
- Keeps the already runtime-tested Xbox / Microsoft Store path behind its exact PE fingerprint and stronger live identity validation.
- Requires the resolved main-thread ID to belong to the current KCD2 process and verifies IGame -> IGameFramework -> ISystem identity before installing version-specific hooks.
- Unknown or mismatched builds fail closed with no version-specific Clean Pause hooks installed.
- Adds executable Windows tests for storefront/build matching, gEnv resolution, fail-closed cases, and Warhorse whdlversions.json path/parsing behavior.
- Corrects ASI-loader installation guidance so KCD2CleanPause.asi is installed in a location actually scanned by the active loader.

## Compatibility status

- **Xbox / Microsoft Store 1.5.6:** Clean Pause runtime-tested from the existing accepted runtime path.
- **Steam 1.5.6 release_1_5-15693:** exact binary profile implemented and automatically validated; this RC is intended to complete the in-game Clean Pause smoke test.
- **GOG 1.5.6 release_1_5-15693:** compatibility profile implemented from distribution-specific reverse-engineering and external runtime evidence; Clean Pause-specific in-game smoke QA has not yet been completed by this project.
- **Epic Games Store 1.5.6 release_1_5-15693:** compatibility profile implemented from distribution-specific reverse-engineering and external runtime evidence; Clean Pause-specific in-game smoke QA has not yet been completed by this project.

This prerelease should not be interpreted as a claim that every listed storefront has already completed Clean Pause-specific runtime acceptance.

## Steam smoke test requested

For the reported Steam 1.5.6 build:

1. install the ASI package using the included INSTALL.txt;
2. launch the game and load into gameplay;
3. press Escape and confirm Clean Pause keeps the current gameplay view/HUD/subtitles visible;
4. press Escape again and confirm the ordinary vanilla pause menu appears;
5. if using an Xbox controller, repeat with Start and verify B reveals the vanilla pause menu from Clean Pause;
6. resume normally and confirm gameplay continues;
7. if anything fails, attach kcd2_clean_pause_native.log from beside KCD2CleanPause.asi.

## Published package

The GitHub prerelease publishes only:

- kcd2-clean-pause-v0.3.0-rc.1-asi.zip
- SHA256SUMS.txt

The ASI ZIP contains:

- KCD2CleanPause.asi — Clean Pause plugin;
- dinput8.dll — pinned official x64 Ultimate ASI Loader;
- INSTALL.txt — installation/removal instructions;
- ASI_LOADER_SOURCE.txt — loader provenance and hashes;
- ULTIMATE_ASI_LOADER_LICENSE.txt — upstream MIT license;
- THIRD_PARTY_NOTICES.txt — third-party notices for distributed components.

## Standalone version.dll status

A new standalone version.dll is not published while Defender investigation #38 remains unresolved. The standalone target continues to build and validate in CI, but it remains an internal CI artifact only.

## Promotion to stable v0.3.0

If the Steam smoke test confirms normal loading and accepted Clean Pause behavior, the same runtime implementation can be promoted through a separate immutable v0.3.0 release-preparation commit. The v0.3.0-rc.1 tag and prerelease will remain immutable history.

The stable Nexus Mods update should be made only after that acceptance step and should use the stable v0.3.0 GitHub release artifact rather than this RC package.
