# Current status and plan

## Release status

- **Stable:** v0.2.2 ASI, runtime-tested on KCD2 1.5.6 Xbox / Microsoft Store.
- **GitHub prerelease candidate:** v0.3.0-rc.2 ASI, current Steam acceptance candidate for multi-store KCD2 1.5.6 compatibility.
- **Standalone version.dll:** still built and validated, but new public distribution remains blocked by Defender investigation #38. The last published standalone package is v0.2.0.

Nexus remains on stable v0.2.2 until a Steam acceptance candidate completes the intended Clean Pause smoke test and stable v0.3.0 is published.

## Steam report history

v0.2.2 exposed two independent Steam problems:

1. old shared-loader instructions could leave dinput8.dll and KCD2CleanPause.asi in different directories, preventing the loader from discovering the plugin;
2. after correct loading, the writable-memory gEnv scanner could accept a false-positive object and observe invalid framework/input/UI state.

v0.3.0-rc.1 fixed that discovery problem. The tester's real Steam 1.5.6 run:

- matched fingerprint 0x6a350e20 / 0x05b2d000 / 0;
- detected Steam release_1_5-15693;
- selected the intended Steam profile;
- independently validated canonical gEnv RVA 0x492D7F8;
- did not crash;
- nevertheless installed no hooks because strong live runtime validation did not finish before RC1's bounded startup-readiness window expired.

Public Steam 1.5.6 reverse-engineering was rechecked after that result. The gEnv layout and all bootstrap slots used by Clean Pause match the release_1_5 ABI currently implemented: IScriptSystem, IInput::PostInputEvent, IGame, IGameFramework::PauseGame/GetISystem, IFlashUI, and mMainThreadId. No static ABI mismatch was found.

## v0.3.0-rc.2 change

RC2 treats build identity and runtime readiness separately:

1. exact Steam/GOG/Epic build/profile/environment evidence must still pass first;
2. once an exact supported profile and canonical gEnv are established, Clean Pause waits for the required live interfaces for the lifetime of the process rather than permanently disabling itself after 120 seconds;
3. polling is 100 ms during the initial startup window and 1 second afterward;
4. hooks remain forbidden until all existing strong gates pass;
5. readiness logs identify the exact current stage and observed interface pointers whenever the reason changes, with a 30-second heartbeat;
6. the already runtime-tested Xbox / Microsoft Store legacy path keeps its existing bounded behavior in this RC.

This is a lifecycle fix, not a relaxation of fail-closed compatibility checks.

## Compatibility profiles

| Storefront | KCD2 build evidence | Clean Pause status |
| --- | --- | --- |
| Xbox / Microsoft Store | exact PE fingerprint 0x6a391f7b / 0x05bf2000 / 0 | runtime-tested baseline |
| Steam | exact PE fingerprint 0x6a350e20 / 0x05b2d000 / 0; canonical gEnv RVA 0x492D7F8 | RC2 smoke-test target; RC1 confirmed profile/environment identity and no crash |
| GOG | Galaxy64.dll marker + release_1_5-15693; canonical gEnv RVA 0x49177F8 | profile implemented; Clean Pause smoke QA pending |
| Epic Games Store | EOSSDK-Win64-Shipping.dll marker + release_1_5-15693 + timestamp 0x6A34F917; canonical gEnv RVA 0x491D8B8 | profile implemented; Clean Pause smoke QA pending |

Steam/GOG/Epic share the documented release_1_5 ABI family but use separate shipped binaries and distribution-specific environment evidence.

## Safety contract

1. KCD2 remains the sole pause owner.
2. Storefront, shipped-build identity, ABI, environment discovery, and live readiness are separate concerns.
3. An incompatible future ABI is rejected before hooks.
4. Steam/GOG/Epic use explicit distribution-specific canonical gEnv evidence; Steam additionally cross-checks the captured code anchor once.
5. The main-thread ID must belong to the current process.
6. IGame must identify kcd2.
7. IGame -> IGameFramework -> ISystem must resolve back to the same ISystem as gEnv.
8. Unknown/mismatched builds install no version-specific Clean Pause hooks.
9. Waiting longer for a known exact profile never bypasses any gate.

See docs/RUNTIME_COMPATIBILITY.md for the full evidence and extension model.

## Automated validation

The RC2 candidate is covered by:

- repository/source contract tests;
- x64 MSVC production builds;
- executable Windows runtime-profile tests;
- PE/storefront/build matching and fail-closed tests;
- exact environment-RVA validation;
- Steam one-time anchor/RVA agreement and ambiguity rejection;
- real whdlversions.json parser/path fixtures for build-code detection;
- explicit contract coverage that exact-profile readiness is persistent but backs off after startup;
- explicit contract coverage for stage-specific readiness diagnostics;
- validation of both ASI and standalone native artifacts;
- full release-shaped packaging checks.

## Steam acceptance test

For v0.3.0-rc.2:

1. game reaches the main menu and loads gameplay;
2. Escape enters Clean Pause without covering the gameplay view;
3. HUD/dialogue subtitles and active overhead speech remain preserved as applicable;
4. retained frame remains sharp without pause DoF blur;
5. second Escape reveals the ordinary vanilla pause menu;
6. Xbox Start/B path behaves according to the accepted contract when a controller is available;
7. normal resume works;
8. native log shows the Steam profile reaches runtime validation and hook installation.

If something still prevents hook installation, RC2 should identify the specific readiness gate directly in the log rather than requiring another broad diagnostic probe.

## Nexus Mods plan

Nexus currently remains on stable v0.2.2 and should continue to describe Xbox / Microsoft Store as the runtime-tested storefront for that immutable release.

After Steam acceptance:

1. prepare stable v0.3.0 from the accepted runtime;
2. publish the stable GitHub release through the normal immutable release workflow;
3. update Nexus copy/version/compatibility wording;
4. upload only the stable v0.3.0 ASI GitHub release artifact.

GOG/Epic may be described as implemented compatibility profiles unless/until Clean Pause-specific smoke QA supports stronger runtime-tested wording.

## Remaining engineering work

Before stable v0.3.0:

- complete the focused Steam v0.3.0-rc.2 smoke test;
- review the resulting native log if anything is unexpected;
- promote to stable only if no runtime change is needed.

Blocking new standalone distribution:

- resolve Defender issue #38 before publishing a new standalone version.dll asset.

Non-blocking follow-up:

- GOG/Epic Clean Pause-specific smoke QA;
- coexistence with additional real KCD2 ASI plugins;
- broader cutscene/dialogue and repeated-cycle/load-transition robustness;
- process-lifetime hook/hot-unload policy in #37;
- remove the profiled translation-unit wrapper in #45 after compatibility smoke QA.

## Decision rule

> Reuse vanilla KCD2 pause ownership, select binary compatibility from explicit evidence, and prefer a visible vanilla-menu fallback or no hooks at all over unverified state manipulation.
