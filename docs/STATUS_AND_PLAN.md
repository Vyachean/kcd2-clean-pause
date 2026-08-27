# Current status and plan

## Release status

**v0.2.2** is the current public ASI release.

The Clean Pause runtime is unchanged from v0.2.1 and was tested with **KCD2 1.5.6 on the PC Xbox Store / Xbox app version**, using an Xbox controller and the upstream Ultimate ASI Loader.

Distribution status is per edition:

- **`KCD2CleanPause.asi`: supported / retail-accepted** and packaged with the pinned official x64 Ultimate ASI Loader for a complete fresh installation;
- **standalone `version.dll`: built and validated but new distribution withheld** while Defender investigation #38 is unresolved. The last published standalone package remains v0.2.0.

## v0.2.2 scope

v0.2.2 is a packaging-only release:

- bundles the official x64 Ultimate ASI Loader with the ASI ZIP;
- pins upstream v9.7.4, source commit, release asset, and SHA-256;
- validates the upstream archive and extracted x64 `dinput8.dll` during release packaging;
- includes loader provenance and its MIT license;
- preserves the shared-loader installation path for users who already have a compatible `dinput8.dll`.

No runtime retest was required solely for this packaging change because the Clean Pause binary behavior is unchanged from the accepted v0.2.1 runtime.

## Accepted runtime behavior

- Xbox Start enters the vanilla-owned Clean Pause without drawing the normal pause menu;
- simulation/picture and ongoing dialogue audio pause together immediately;
- main HUD and dialogue subtitles remain retained without the previous hide/restore blink;
- the retained frame is sharp without vanilla pause DoF blur;
- active NPC overhead subtitles remain preserved;
- second Start or B reveals the already-open vanilla pause menu;
- closing the menu and resuming returns to normal gameplay.

The transition fix is implemented by restricting HUD/subtitle presentation ownership to KCD2's actual validated `IGameFramework::PauseGame(true, ...)` transition. Pending Start/release correlation by itself performs no Flash replay.

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

## Accepted runtime architecture

1. KCD2 is the sole pause owner.
2. Physical Escape/Start input is forwarded to KCD2.
3. The verified target `IGameFramework::PauseGame(true, ...)` call is the preferred transition barrier; all vanilla arguments are forwarded unchanged.
4. Pending input correlation alone does not pin HUD/subtitle presentation.
5. `Menu@0` remains logically visible; only `Menu@0::Render()` is suppressed during Clean Pause.
6. Gameplay presentation snapshots preserve exact root `hud@0` visibility plus the 28 HUD-child visibility booleans.
7. The no-blink transaction reads authoritative vanilla child visibility from `I_UIHudMask::IsElementVisible` and never reconstructs complete vanilla state from a partial Flash mutation.
8. Global HUD-mask/bubble method detours are scoped to exact discovered runtime instances.
9. `IUIElement::GetMovieClip()` results are borrowed/call-local and never retained or released by the mod.
10. Subtitle-clearing Flash calls are narrowly suppressed only during the actual transition / active Clean Pause.
11. `wh_cl_NearDof` and `r_DepthOfField` are restored before visible vanilla presentation.
12. Unresolved core state fails open to visible vanilla pause.

## Repository structure

The supported implementation is the native runtime under `native/`. Superseded Lua/profile prototypes and their builders/fixtures are no longer present in the current production tree. Historical research and retail evidence are isolated under `docs/history/`.

## Nexus Mods readiness

The GitHub release stage is complete:

- immutable tag/release `v0.2.2` has been published;
- public main file: `kcd2-clean-pause-v0.2.2-asi.zip`;
- Nexus page copy and upload checklist are prepared in `docs/NEXUS.md`;
- the CI-only standalone `version.dll` package must not be uploaded while #38 remains unresolved.

There is no remaining runtime or packaging blocker for publishing the ASI edition on Nexus Mods.

## Remaining engineering work

Blocking new standalone distribution:

- resolve Defender issue #38 and record an independent/Microsoft false-positive verdict before publishing a new `version.dll` asset.

Compatibility hardening:

- strict `WHGame.dll` fingerprint enforcement remains tracked in #36;
- capture/revalidate ABI evidence when game builds change.

Non-blocking follow-up:

- verify coexistence with additional real KCD2 ASI plugins;
- investigate safe direct B resume only if a canonical vanilla mechanism is found;
- broader cutscene/dialogue and repeated-cycle/load-transition robustness;
- process-lifetime hook/hot-unload policy remains tracked in #37.

## Decision rule

> Reuse vanilla KCD2 pause ownership, scope presentation changes to the real pause transition, and prefer a visible vanilla-menu fallback over unverified state manipulation.
