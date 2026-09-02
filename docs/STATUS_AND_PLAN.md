# Current status and plan

## Release status

- **Stable:** v0.2.2 ASI, runtime-tested on KCD2 1.5.6 Xbox / Microsoft Store.
- **GitHub prerelease candidate:** v0.3.0-rc.4 ASI, lifecycle-hardened Steam acceptance candidate.
- **Standalone version.dll:** still built and validated, but new public distribution remains blocked by Defender investigation #38. The last published standalone package is v0.2.0.

Nexus remains on stable v0.2.2 until the Steam acceptance candidate completes the intended Clean Pause smoke test and stable v0.3.0 is published.

## Steam report history and root cause

v0.2.2 exposed two independent Steam problems:

1. old shared-loader instructions could leave dinput8.dll and KCD2CleanPause.asi in different directories, preventing the loader from discovering the plugin;
2. after correct loading, the writable-memory gEnv scanner could accept a false-positive object and observe invalid framework/input/UI state.

v0.3.0-rc.1 fixed the discovery problem. The reporter's real Steam 1.5.6 run matched the exact fingerprint/profile, validated canonical gEnv RVA 0x492D7F8, and no longer crashed, but the profiled bootstrap still installed no hooks.

RC2 removed the permanent startup-readiness deadline and added precise readiness diagnostics. Further comparison with working libKCD2/KCSE native mods then exposed the actual remaining framework error:

- Steam `IGame` vtable slot 16 is not a verified `IGameFramework` accessor; detailed RE identifies it as another engine-root object.
- Working libKCD2 mods obtain framework functionality from `CCryAction::GetInstance()`.
- On Steam 1.5.6 the canonical `IGameFramework` pointer is cached at qword_18549D328 (RVA 0x0549D328).
- Clean Pause's mature runtime already designed the PauseGame observer as optional, but the profiled bootstrap accidentally promoted framework resolution to a mandatory precondition for installing the input hook.

RC3 corrected framework identity and restored the optional capability boundary. A second implementation review found one remaining lifecycle weakness: Steam still attempted the optional observer only once during bootstrap, so a not-yet-published CCryAction singleton could permanently leave the stronger barrier unavailable even though the core runtime continued through its fallback.

## v0.3.0-rc.4 change

RC4 removes that timing dependency without changing the accepted Clean Pause semantics:

1. The required `PostInputEvent` hook is installed independently and first; failed enable is rolled back cleanly.
2. Steam does not install the PauseGame observer from bootstrap after the input hook becomes live.
3. On a real Escape/Start press, on the validated KCD2 input thread and before forwarding to vanilla, Clean Pause resolves the canonical CCryAction singleton and installs the optional PauseGame observer.
4. If the singleton is still unavailable, the existing Menu/input fallback remains active and a later Pause press retries the observer.
5. Steam has one observer-installation path, avoiding a duplicate-create race between bootstrap and first input.
6. The compatibility wrapper protects its direct engine `InputEvent` reads with SEH and otherwise delegates unchanged to the mature input implementation.
7. Xbox / Microsoft Store retains the existing runtime-tested legacy discovery/framework path.
8. GOG/Epic never fall back to the invalid slot-16 framework assumption and remain on the core input/Menu path until canonical framework locators are registered.

## Compatibility profiles

| Storefront | KCD2 build evidence | Clean Pause status |
| --- | --- | --- |
| Xbox / Microsoft Store | exact PE fingerprint 0x6a391f7b / 0x05bf2000 / 0 | runtime-tested baseline |
| Steam | exact PE fingerprint 0x6a350e20 / 0x05b2d000 / 0; gEnv RVA 0x492D7F8; CCryAction framework storage RVA 0x0549D328 | RC4 smoke-test target; RC1 already confirmed profile/gEnv and no crash |
| GOG | Galaxy64.dll marker + release_1_5-15693; gEnv RVA 0x49177F8 | core profile implemented; Clean Pause smoke QA pending |
| Epic Games Store | EOSSDK-Win64-Shipping.dll marker + release_1_5-15693 + timestamp 0x6A34F917; gEnv RVA 0x491D8B8 | core profile implemented; Clean Pause smoke QA pending |

## Safety contract

1. KCD2 remains the sole pause owner.
2. Storefront, shipped-build identity, ABI, environment discovery, and optional capabilities are separate concerns.
3. Unknown/mismatched builds and unsupported future ABIs install no version-specific hooks.
4. Steam/GOG/Epic require their distribution-specific canonical gEnv evidence; Steam also cross-checks its captured code anchor.
5. Required input/script/game/system/FlashUI objects and main-thread ownership must validate before the core runtime is installed.
6. IGame must identify `kcd2`.
7. Framework/PauseGame observation is optional and cannot suppress the proven input/Menu fallback.
8. When Steam framework is available, it must be the canonical CCryAction singleton and `GetISystem()` must agree with gEnv before PauseGame is hooked.
9. Steam acquires that optional observer only through the validated Pause-input path after core input installation; Xbox keeps its already runtime-tested legacy path isolated from non-Xbox builds.
10. Retail-captured KCD2 controller IDs remain authoritative for Clean Pause: `xi_start=516`, `xi_a=526`, `xi_b=527`.

## Automated validation

RC4 is covered by:

- repository/source contract tests;
- x64 MSVC production builds;
- executable Windows runtime-profile tests;
- PE/storefront/build matching and fail-closed tests;
- exact environment-RVA validation;
- Steam anchor/RVA agreement and ambiguity rejection;
- real whdlversions.json parser/path fixtures;
- contract coverage that non-Xbox exact-profile readiness does not depend on `IGame[16]` framework discovery;
- contract coverage for Steam CCryAction framework storage/vtable/system identity;
- contract coverage that the required input hook is installed before optional framework capability;
- contract coverage for the single lazy Steam observer-installation path and SEH-protected profiled input reads;
- validation of both ASI and standalone native artifacts;
- full release-shaped packaging checks.

The runtime hardening commit passed both Validate and Release-shaped PR workflows before merge to main. The release-preparation PR must pass the same gates again before rc.4 is published.

## Steam acceptance test

For v0.3.0-rc.4:

1. game reaches the main menu and loads gameplay;
2. Escape enters Clean Pause without covering the gameplay view;
3. HUD/dialogue subtitles and active overhead speech remain preserved as applicable;
4. retained frame remains sharp without pause DoF blur;
5. second Escape reveals the ordinary vanilla pause menu;
6. Xbox Start/B path behaves according to the accepted contract when a controller is available;
7. normal resume works;
8. native log shows the Steam profile reaches core hook installation before framework capability is needed and normally shows the canonical PauseGame observer becoming active on the first Pause input.

## Nexus Mods plan

Nexus remains on stable v0.2.2. After Steam acceptance:

1. prepare stable v0.3.0 from the accepted runtime;
2. publish the stable GitHub release through the normal immutable release workflow;
3. update Nexus copy/version/compatibility wording;
4. upload only the stable v0.3.0 ASI GitHub release artifact.

GOG/Epic may be described as implemented compatibility profiles unless/until Clean Pause-specific smoke QA supports stronger runtime-tested wording.

## Remaining engineering work

Before stable v0.3.0:

- complete the focused Steam v0.3.0-rc.4 smoke test;
- review the native log only if behavior is unexpected;
- promote to stable if accepted.

Blocking new standalone distribution:

- resolve Defender issue #38 before publishing a new standalone version.dll asset.

Non-blocking follow-up:

- add canonical GOG/Epic framework locators if their PauseGame barrier is desired rather than relying on the Menu fallback;
- GOG/Epic Clean Pause-specific smoke QA;
- coexistence with additional real KCD2 ASI plugins;
- broader cutscene/dialogue and repeated-cycle/load-transition robustness;
- process-lifetime hook/hot-unload policy in #37;
- remove the profiled translation-unit wrapper in #45 after compatibility smoke QA.

## Decision rule

> Reuse vanilla KCD2 pause ownership, select binary compatibility from explicit evidence, keep optional capabilities optional, and prefer a visible vanilla-menu fallback or no hooks over unverified state manipulation.
