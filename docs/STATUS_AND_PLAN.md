# Current status and plan

## Release status

- **Stable:** v0.2.2 ASI, runtime-tested on KCD2 1.5.6 Xbox / Microsoft Store.
- **Published GitHub prerelease:** v0.3.0-rc.4 ASI.
- **Current source:** Steam 1.5.6 `release_1_5-15693` runtime acceptance is complete on `main` after PR #51.
- **GOG / Epic Games Store:** fail-closed profiles are implemented from distribution-specific evidence; Clean Pause-specific smoke QA is still pending.
- **Standalone version.dll:** still built and validated, but new public distribution remains withheld.
- **Stable v0.3.0 / any new public native candidate:** blocked by Defender / Smart App Control investigation #38. The accepted current-source ASI still reproduces the ML/heuristic detections, so runtime acceptance is not being promoted until the security/reputation investigation is resolved.

Nexus remains on stable v0.2.2 while #38 is unresolved.

## Steam acceptance history

The Steam work exposed several independent assumptions that were safe on the original Xbox runtime but not portable across storefront binaries:

1. the old writable-memory `gEnv` scan could accept a false-positive object;
2. Steam `IGame[16]` is not a verified `IGameFramework` accessor;
3. the canonical Steam `CCryAction` singleton may not be ready during bootstrap;
4. Steam returns `IGame::GetName() == "KCD2"` while the captured Xbox runtime returns `"kcd2"`;
5. visible vanilla pause-menu Escape repeats could re-enter Clean Pause preparation;
6. the original gameplay HUD snapshot synchronously queried 28 Scaleform clips on every physical pause press, causing a visible pre-pause hitch;
7. Steam pause presentation could change root/menu rendering during the short handoff before Clean Pause ownership was established.

The accepted current-source path now:

- matches the exact Steam PE fingerprint `0x6a350e20 / 0x05b2d000 / 0`;
- validates canonical `gEnv` at RVA `0x0492D7F8` with the independent console-storage anchor cross-check;
- resolves the optional real `IGameFramework` from canonical `CCryAction` storage RVA `0x0549D328` and verifies its vtable/system identity;
- acquires the optional PauseGame observer lazily on a real Pause input, avoiding bootstrap timing races;
- accepts only the two observed retail `IGame::GetName()` spellings (`kcd2` and `KCD2`) while keeping all other build gates strict;
- forwards an already-visible vanilla pause-menu Escape/Start gesture through its matching release without Clean Pause preparation;
- keeps KCD2 as the sole pause owner and observes `PauseGame(true)` without synthesizing pause calls;
- captures gameplay HUD visibility from authoritative `C_UIHudMask` state after that transaction has been validated, with the old 28-clip Flash walk retained only as fallback;
- preserves Steam root HUD visibility across the verified pause transition and provisionally suppresses Menu rendering through the handoff with fail-open rollback.

Runtime QA confirms the intended Steam lifecycle: first Escape enters Clean Pause, second Escape reveals the already-open vanilla pause menu, Escape from the visible menu resumes promptly, and the recurring pre-pause setup cost dropped from roughly 170-203 ms to 0-16 ms on warm entries.

A residual single visual frame can still appear when the gameplay HUD is restored after KCD2 is already paused. It is accepted as non-blocking and tracked separately in #52.

## Compatibility profiles

| Storefront | KCD2 build evidence | Framework capability | Clean Pause status |
| --- | --- | --- | --- |
| Xbox / Microsoft Store | exact PE fingerprint `0x6a391f7b / 0x05bf2000 / 0` | retained runtime-tested legacy `IGame[16]` adapter | runtime-tested baseline; current-source regression smoke recommended before next public native release |
| Steam | exact PE fingerprint `0x6a350e20 / 0x05b2d000 / 0`; gEnv RVA `0x492D7F8` | canonical CCryAction storage `0x0549D328`, optional but strongly validated | runtime-accepted on current source |
| GOG | `Galaxy64.dll` + `release_1_5-15693`; gEnv RVA `0x49177F8` | no canonical locator registered; Menu/input fallback remains available | profile implemented; Clean Pause smoke QA pending |
| Epic Games Store | `EOSSDK-Win64-Shipping.dll` + `release_1_5-15693` + timestamp `0x6A34F917`; gEnv RVA `0x491D8B8` | no canonical locator registered; Menu/input fallback remains available | profile implemented; Clean Pause smoke QA pending |

## Safety contract

1. KCD2 remains the sole pause owner.
2. Storefront, shipped-build identity, ABI, environment discovery and optional capabilities are separate concerns.
3. Unknown/mismatched builds and unsupported future ABIs install no version-specific hooks.
4. Steam/GOG/Epic require their distribution-specific canonical `gEnv` evidence; Steam additionally cross-checks its captured code anchor.
5. Required script/input/game/system/FlashUI objects and main-thread ownership must validate before the core runtime is installed.
6. `IGame::GetName()` must match an observed supported retail identity (`kcd2` or `KCD2`).
7. Framework/PauseGame observation is optional and cannot suppress the proven PostInputEvent/Menu fallback.
8. When Steam framework is available, it must be the canonical CCryAction singleton and `GetISystem()` must agree with `gEnv` before PauseGame is hooked.
9. Steam acquires that optional observer only through the validated Pause-input path after core input installation; Xbox keeps its separately proven legacy adapter isolated from non-Xbox builds.
10. HUD presentation is restored from authoritative `C_UIHudMask` state whenever that transaction is available; partial or unverifiable presentation ownership fails open to the vanilla menu.
11. Native hooks are process-lifetime state. Hot DLL unload/reload is unsupported; `Stop()` is process-teardown signaling, not complete hook removal.
12. Retail-captured controller IDs remain authoritative for Clean Pause: `xi_start=516`, `xi_a=526`, `xi_b=527`.

## Automated validation

Current source is covered by:

- repository/source contract tests;
- x64 MSVC production builds;
- executable Windows runtime-profile tests;
- PE/storefront/build matching and fail-closed tests;
- exact environment-RVA validation;
- Steam anchor/RVA agreement and ambiguity rejection;
- real `whdlversions.json` parser/path fixtures;
- contract coverage that non-Xbox readiness never depends on the Xbox `IGame[16]` assumption;
- Steam CCryAction framework storage/vtable/system identity checks;
- required-input-hook vs optional-framework capability ordering;
- the single lazy Steam observer-installation path and SEH-protected profiled input reads;
- visible-menu whole-gesture passthrough;
- Steam root-visibility/render-handoff contracts;
- authoritative `C_UIHudMask` gameplay snapshot plus Flash fallback;
- complete rollback when a created MinHook detour fails to enable;
- validation and packaging of both native editions.

PR #51 passed Validate and Release-shaped workflows before merge; `main` passed both workflows again after the squash merge, with public release publication correctly skipped.

## Release blocker: #38

The current accepted runtime must not be promoted solely because gameplay acceptance succeeded. The final `main` ASI is unsigned and still receives current ML/heuristic detections, including Microsoft, Cynet and Symantec reports. Smart App Control has also blocked an earlier exact ASI sample before it could load.

Until #38 is resolved:

- do not publish stable v0.3.0 from the same unresolved native-binary line;
- do not ask users to disable Smart App Control, Defender or add exclusions;
- do not try to evade detections through packing, obfuscation, renamed payloads or similar AV-bypass changes;
- submit exact candidate binaries to the relevant vendors as suspected false positives and record their submission IDs/verdicts;
- keep historical immutable releases unchanged.

## Before the next public native release

Required:

- resolve or explicitly review #38 with the security vendors for the exact candidate binary;
- perform one focused Xbox / Microsoft Store regression smoke on current source because shared HUD/presentation code changed after the original Xbox stable acceptance;
- rerun Validate and Release-shaped CI on the exact candidate commit;
- confirm Steam acceptance remains unchanged after any binary-affecting fixes made for reasons other than AV evasion.

Non-blocking follow-up:

- residual one-frame HUD restore presentation (#52);
- GOG/Epic Clean Pause-specific smoke QA and canonical framework locators if stronger PauseGame barriers are desired;
- coexistence with additional real KCD2 ASI plugins;
- broader cutscene/dialogue and repeated-cycle/load-transition robustness;
- remove the profiled translation-unit wrapper in #45 after the current runtime line is frozen and regression-smoked;
- deduplicate common Win32 memory/RTTI/MinHook helpers as part of that behavior-preserving architecture refactor.

## Architecture debt policy

The compatibility wrapper in #45 is acknowledged production debt: `clean_pause_native_profiled.cpp` macro-renames legacy bootstrap symbols and textually includes the mature core translation unit. It was deliberately kept during storefront acceptance to minimize behavior change. Do not combine its removal with compatibility or security/reputation fixes. The eventual refactor should establish normal internal APIs between build discovery/adapters and the shared Clean Pause core without changing accepted runtime behavior.

## Decision rule

> Reuse vanilla KCD2 pause ownership, select binary compatibility from explicit evidence, keep optional capabilities optional, and prefer a visible vanilla-menu fallback or no hooks over unverified state manipulation.
