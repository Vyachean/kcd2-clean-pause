# KCD2 Clean Pause v0.3.0-rc.2

Second release candidate for **Kingdom Come: Deliverance II 1.5.6** multi-store compatibility on Windows.

v0.3.0-rc.1 fixed the original Steam crash-class discovery problem: the tester's Steam build matched the exact fingerprint, selected the correct Steam profile, validated the canonical `gEnv`, and no longer crashed. However, RC1 permanently disabled Clean Pause when all live runtime interfaces had not passed strong validation within the startup readiness window.

RC2 fixes that lifecycle behavior without weakening any compatibility or identity gate.

## What changed since rc.1

- Exact-profile Steam/GOG/Epic builds no longer permanently disable Clean Pause after the previous 120-second readiness window.
- Runtime readiness keeps waiting for the lifetime of the process once an exact supported build/profile and canonical `gEnv` have been validated.
- Polling remains at 100 ms during the initial startup window, then backs off to 1 second.
- Strong validation still requires the documented release_1_5 ABI, current-process main thread, `IGame` identity, valid `IGameFramework` surface, and `IGameFramework -> ISystem` agreement before hooks.
- Readiness diagnostics now report the exact failing stage and observed environment/interface pointers whenever the state changes, with a 30-second heartbeat while still waiting.
- The already runtime-tested Xbox / Microsoft Store path retains its bounded legacy discovery behavior in this RC.

## Compatibility status

- **Xbox / Microsoft Store 1.5.6:** Clean Pause runtime-tested baseline.
- **Steam 1.5.6 release_1_5-15693:** exact profile and canonical environment identity confirmed by the RC1 tester; RC2 is the current in-game acceptance candidate.
- **GOG 1.5.6 release_1_5-15693:** compatibility profile implemented from distribution-specific reverse-engineering and external runtime evidence; Clean Pause-specific smoke QA is still pending.
- **Epic Games Store 1.5.6 release_1_5-15693:** compatibility profile implemented from distribution-specific reverse-engineering and external runtime evidence; Clean Pause-specific smoke QA is still pending.

Unknown or mismatched builds remain fail closed and receive no version-specific Clean Pause hooks.

## Steam smoke test requested

For the reported Steam 1.5.6 build:

1. install the ASI package using the included INSTALL.txt;
2. launch the game and load into gameplay;
3. press Escape and confirm Clean Pause keeps the current gameplay view/HUD/subtitles visible;
4. press Escape again and confirm the ordinary vanilla pause menu appears;
5. if using an Xbox controller, repeat with Start and verify B reveals the vanilla pause menu from Clean Pause;
6. resume normally and confirm gameplay continues;
7. if anything fails, attach `kcd2_clean_pause_native.log` from beside `KCD2CleanPause.asi`.

The RC2 log is intentionally more specific than RC1: a remaining compatibility failure should identify the exact readiness gate rather than only reporting a generic validation timeout.

## Published package

The GitHub prerelease publishes only:

- `kcd2-clean-pause-v0.3.0-rc.2-asi.zip`
- `SHA256SUMS.txt`

The ASI ZIP contains:

- `KCD2CleanPause.asi` — Clean Pause plugin;
- `dinput8.dll` — pinned official x64 Ultimate ASI Loader;
- `INSTALL.txt` — installation/removal instructions;
- `ASI_LOADER_SOURCE.txt` — loader provenance and hashes;
- `ULTIMATE_ASI_LOADER_LICENSE.txt` — upstream MIT license;
- `THIRD_PARTY_NOTICES.txt` — third-party notices for distributed components.

## Standalone version.dll status

A new standalone `version.dll` is not published while Defender investigation #38 remains unresolved. The standalone target continues to build and validate in CI, but it remains an internal CI artifact only.

## Promotion to stable v0.3.0

If the Steam smoke test confirms normal loading and accepted Clean Pause behavior, the accepted runtime can be promoted through a separate immutable v0.3.0 release-preparation commit. The v0.3.0-rc.1 and v0.3.0-rc.2 tags/releases remain immutable history.

The stable Nexus Mods update should be made only after that acceptance step and should use the stable v0.3.0 GitHub release artifact rather than an RC package.
