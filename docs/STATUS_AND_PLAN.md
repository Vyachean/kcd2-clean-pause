# Current status and plan

## Release status

- **Stable:** v0.2.2 ASI, runtime-tested on KCD2 1.5.6 Xbox / Microsoft Store.
- **GitHub prerelease candidate:** v0.3.0-rc.1 ASI, prepared from PR #44 for multi-store KCD2 1.5.6 compatibility.
- **Standalone version.dll:** still built and validated, but new public distribution remains blocked by Defender investigation #38. The last published standalone package is v0.2.0.

v0.3.0-rc.1 is intentionally a prerelease. Its immediate purpose is to let the Steam reporter test the final profiled runtime through the normal GitHub release artifact rather than through an ad-hoc diagnostic build.

If the Steam smoke test confirms accepted Clean Pause behavior, prepare a separate immutable stable v0.3.0 release using the same runtime implementation, then update Nexus Mods from that stable GitHub artifact. Do not upload the RC itself to Nexus as the final release.

## Steam report and root cause

The Steam report exposed two separate v0.2.2 problems:

1. the old shared-loader instructions could leave dinput8.dll and KCD2CleanPause.asi in different directories, so Ultimate ASI Loader never discovered the plugin;
2. after correct loading, v0.2.2's writable-memory gEnv scanner could accept a false-positive object on Steam, producing invalid framework/input/UI observations.

The report provided the Steam KCD2 1.5.6 fingerprint and enough evidence to identify the discovery defect. PR #44 replaces that unsafe cross-build assumption with explicit build/storefront/ABI profiles and fail-closed validation.

## v0.3.0-rc.1 compatibility profiles

| Storefront | KCD2 build evidence | Clean Pause status |
| --- | --- | --- |
| Xbox / Microsoft Store | exact PE fingerprint 0x6a391f7b / 0x05bf2000 / 0 | runtime-tested baseline |
| Steam | exact PE fingerprint 0x6a350e20 / 0x05b2d000 / 0; canonical gEnv RVA 0x492D7F8 | RC smoke-test target |
| GOG | Galaxy64.dll marker + release_1_5-15693; canonical gEnv RVA 0x49177F8 | profile implemented; Clean Pause smoke QA pending |
| Epic Games Store | EOSSDK-Win64-Shipping.dll marker + release_1_5-15693 + timestamp 0x6A34F917; canonical gEnv RVA 0x491D8B8 | profile implemented; Clean Pause smoke QA pending |

Steam/GOG/Epic share the documented release_1_5 ABI family but use separate shipped binaries and distribution-specific environment evidence.

## Runtime compatibility architecture

1. KCD2 remains the sole pause owner.
2. Storefront, shipped-build identity, ABI and environment discovery are separate dimensions.
3. The mature runtime adapter supports the documented KCD2 release_1_5 / 1.5.6 ABI only; an incompatible future ABI is rejected before hooks.
4. Steam/GOG/Epic use explicit distribution-specific canonical gEnv evidence. Steam additionally cross-checks the captured code anchor once.
5. Xbox keeps the already runtime-tested discovery path only behind the exact Xbox fingerprint.
6. Profiled immutable environment identity is resolved once before readiness polling; the 100 ms loop no longer repeatedly scans WHGame.dll.
7. The main-thread ID must belong to the current process, IGame must identify kcd2, and IGame -> IGameFramework -> ISystem must resolve back to the same ISystem as gEnv.
8. Unknown/mismatched builds install no version-specific Clean Pause hooks.

See docs/RUNTIME_COMPATIBILITY.md for the full evidence and extension model.

## Automated validation

The v0.3.0-rc.1 candidate is covered by:

- repository/source contract tests;
- x64 MSVC production builds;
- executable Windows runtime-profile tests;
- PE/storefront/build matching and fail-closed tests;
- exact environment-RVA validation;
- Steam one-time anchor/RVA agreement and ambiguity rejection;
- real whdlversions.json parser/path fixtures for build-code detection;
- validation of both ASI and standalone native artifacts;
- full release-shaped packaging checks.

## Steam acceptance test

For v0.3.0-rc.1:

1. game reaches the main menu and loads gameplay;
2. Escape enters Clean Pause without covering the gameplay view;
3. HUD/dialogue subtitles and active overhead speech remain preserved as applicable;
4. retained frame remains sharp without pause DoF blur;
5. second Escape reveals the ordinary vanilla pause menu;
6. Xbox Start/B path behaves according to the accepted contract when a controller is available;
7. normal resume works;
8. native log shows the Steam profile was selected and validated without compatibility fallback/errors.

A single successful focused Steam test is sufficient to proceed to stable v0.3.0 unless it exposes a new issue.

## Nexus Mods plan

Nexus currently remains on stable v0.2.2 and should continue to describe Xbox / Microsoft Store as the runtime-tested storefront for that immutable release.

After Steam acceptance:

1. prepare stable v0.3.0 from the accepted RC runtime;
2. publish the stable GitHub release through the normal immutable release workflow;
3. update Nexus copy/version/compatibility wording;
4. upload only the stable v0.3.0 ASI GitHub release artifact.

GOG/Epic may be described as implemented compatibility profiles unless/until Clean Pause-specific smoke QA supports the stronger runtime-tested wording.

## Remaining engineering work

Before stable v0.3.0:

- complete the focused Steam v0.3.0-rc.1 smoke test;
- review the resulting native log if anything is unexpected;
- promote to stable only if no runtime change is needed.

Blocking new standalone distribution:

- resolve Defender issue #38 before publishing a new standalone version.dll asset.

Non-blocking follow-up:

- GOG/Epic Clean Pause-specific smoke QA;
- coexistence with additional real KCD2 ASI plugins;
- broader cutscene/dialogue and repeated-cycle/load-transition robustness;
- process-lifetime hook/hot-unload policy in #37;
- remove the profiled translation-unit wrapper in #45 after compatibility smoke QA;
- close/rewrite #36 when #44 lands because its strict-build-gating goal is implemented by the profile architecture.

## Decision rule

> Reuse vanilla KCD2 pause ownership, select binary compatibility from explicit evidence, and prefer a visible vanilla-menu fallback or no hooks at all over unverified state manipulation.
