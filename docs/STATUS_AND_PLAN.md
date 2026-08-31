# Current status and plan

## Release status

**v0.2.2** is the current public ASI release.

The public v0.2.2 runtime is unchanged from v0.2.1 and was runtime-tested with **KCD2 1.5.6 on the PC Xbox Store / Xbox app version**, using an Xbox controller and the upstream Ultimate ASI Loader.

PR #44 is the current unreleased compatibility candidate. It fixes the Steam failure reported against v0.2.2 and adds fail-closed KCD2 1.5.6 build profiles for all four known PC storefronts: Steam, GOG, Epic Games Store and Xbox / Microsoft Store.

Distribution status is per edition:

- **`KCD2CleanPause.asi`: current public distribution**, with v0.2.2 runtime-accepted on the Xbox / Microsoft Store 1.5.6 build;
- **unreleased profiled ASI runtime:** Steam/GOG/Epic 1.5.6 binary compatibility is implemented and covered by public RE evidence plus automated Windows tests, but Clean Pause in-game smoke QA remains pending before those storefronts are advertised as runtime-tested by this project;
- **standalone `version.dll`: built and validated but new distribution withheld** while Defender investigation #38 is unresolved. The last published standalone package remains v0.2.0.

## Steam report and root cause

The Steam report exposed two separate problems in v0.2.2:

1. the original shared-loader instructions could leave `dinput8.dll` and `KCD2CleanPause.asi` in different directories, so Ultimate ASI Loader never discovered the plugin;
2. after the loader and plugin were colocated correctly, the native log showed that v0.2.2's writable-memory `gEnv` scanner accepted a false positive on Steam (`mainThread=8`, invalid framework/UI identity, impossible-looking input events).

The user's later isolation test launched normally with the loader and plugin arrangement under test, while Clean Pause still did not work. The resulting native log provided the Steam PE fingerprint and enough evidence to identify the runtime-discovery defect. Further iterative probe builds are not required for reverse engineering.

PR #44 replaces that unsafe cross-build assumption with explicit build/storefront/ABI profiles and strong fail-closed validation.

## v0.2.2 scope

v0.2.2 remains an immutable packaging-only release:

- bundles the official x64 Ultimate ASI Loader with the ASI ZIP;
- pins upstream v9.7.4, source commit, release asset, and SHA-256;
- validates the upstream archive and extracted x64 `dinput8.dll` during release packaging;
- includes loader provenance and its MIT license;
- supports shared compatible ASI loaders, provided `KCD2CleanPause.asi` is installed in a plugin location that the existing loader actually scans.

The existing immutable v0.2.2 ZIP still contains the earlier ambiguous `INSTALL.txt`; current README/Nexus guidance is the corrected installation guidance. The archive itself is not rewritten.

## Accepted runtime behavior

On the runtime-tested Xbox / Microsoft Store build:

- Xbox Start enters the vanilla-owned Clean Pause without drawing the normal pause menu;
- simulation/picture and ongoing dialogue audio pause together immediately;
- main HUD and dialogue subtitles remain retained without the previous hide/restore blink;
- the retained frame is sharp without vanilla pause DoF blur;
- active NPC overhead subtitles remain preserved;
- second Start or B reveals the already-open vanilla pause menu;
- closing the menu and resuming returns to normal gameplay.

The transition fix restricts HUD/subtitle presentation ownership to KCD2's actual validated `IGameFramework::PauseGame(true, ...)` transition. Pending Start/release correlation by itself performs no Flash replay.

## Product contract

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  sharp retained frame, no pause DoF blur
  visible dialogue subtitles remain visible
  active NPC overhead subtitles remain visible
  Escape / Xbox Start -> visible vanilla pause menu
  Xbox B               -> visible vanilla pause menu
```

Direct `Clean Pause -> B -> Running` is not part of the current contract.

## Runtime compatibility architecture

1. KCD2 remains the sole pause owner.
2. Storefront, shipped build identity, ABI and environment discovery are separate dimensions.
3. The mature runtime adapter supports the documented KCD2 `release_1_5 / 1.5.6` ABI only; a future incompatible ABI is rejected by `MatureRuntimeSupports()` before hooks.
4. Xbox / Microsoft Store 1.5.6 is selected by its captured full PE fingerprint and retains the already runtime-tested discovery path behind stronger identity checks.
5. Steam 1.5.6 is selected by its captured full PE fingerprint and uses exact canonical `gEnv` RVA `0x492D7F8`, additionally cross-checked once through the known `exec autoexec.cfg` / `pConsole` code anchor.
6. GOG 1.5.6 is selected by the GOG binary marker plus Warhorse build `release_1_5-15693` and exact canonical `gEnv` RVA `0x49177F8`.
7. Epic 1.5.6 is selected by the Epic binary marker plus build `release_1_5-15693`, timestamp `0x6A34F917`, and exact canonical `gEnv` RVA `0x491D8B8`.
8. Profiled Steam/GOG/Epic `gEnv` identity is resolved once before runtime readiness polling; the 100 ms poll no longer rescans the large `WHGame.dll` code/data image.
9. The main-thread ID must belong to the current process, `IGame::GetName()` must identify `kcd2`, and `IGame -> IGameFramework -> ISystem` must resolve to the same `ISystem` as `gEnv`.
10. Unknown/mismatched builds install no version-specific Clean Pause hooks.

See `docs/RUNTIME_COMPATIBILITY.md` for the evidence model and coverage matrix.

## Automated validation in PR #44

The compatibility candidate includes:

- source-contract tests for Storefront / BuildProfile / AbiProfile / locator separation;
- executable Windows tests for PE parsing, storefront-marker detection and fail-closed matching;
- real parser/path tests for Warhorse `whdlversions.json` using temporary game-directory fixtures rather than preconstructed build IDs only;
- exact-RVA environment tests;
- Steam one-time anchor/RVA cross-validation and ambiguous-anchor rejection;
- GOG/Epic tests that do not assume the Steam-specific instruction pattern when their independent evidence is the exact distribution-specific RVA;
- MSVC x64 builds and validation of both native editions;
- full release packaging validation.

## Nexus Mods readiness

The currently published Nexus/GitHub artifact remains v0.2.2 and should continue to be described as Xbox / Microsoft Store runtime-tested only.

The next native release should update the public compatibility claim only after the intended smoke-QA level is reached. Until then, Steam/GOG/Epic should be described as implemented/validated compatibility candidates, not as Clean Pause runtime-tested storefronts.

The CI-only standalone `version.dll` package must not be uploaded while #38 remains unresolved.

## Remaining engineering work

Before advertising the new storefront profiles as Clean Pause runtime-tested:

- run one focused Steam smoke test of the final PR #44 ASI candidate (load to gameplay, enter Clean Pause, reveal vanilla menu, resume, inspect native log);
- GOG/Epic Clean Pause smoke tests remain desirable before making equally strong storefront-specific runtime-tested claims, although their release_1_5 native ABI/mapping evidence is independently established.

Blocking new standalone distribution:

- resolve Defender issue #38 and record an independent/Microsoft false-positive verdict before publishing a new `version.dll` asset.

Non-blocking follow-up:

- verify coexistence with additional real KCD2 ASI plugins;
- investigate safe direct B resume only if a canonical vanilla mechanism is found;
- broader cutscene/dialogue and repeated-cycle/load-transition robustness;
- process-lifetime hook/hot-unload policy remains tracked in #37;
- after #44 lands, close or rewrite #36 because its original strict-build-gating goal is implemented by the profile architecture.

## Decision rule

> Reuse vanilla KCD2 pause ownership, select binary compatibility from explicit evidence, and prefer a visible vanilla-menu fallback or no hooks at all over unverified state manipulation.
