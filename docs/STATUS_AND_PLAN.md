# Current status and plan

## Release status

**v0.2.1** is the current stable release target for KCD2 1.5.6 Windows retail.

Support/distribution status is per edition:

- **`KCD2CleanPause.asi`: supported / retail-accepted** on the primary PC Xbox Store / Xbox app target using the upstream Ultimate ASI Loader;
- **standalone `version.dll`: built and validated but v0.2.1 distribution withheld** while Defender investigation #38 is unresolved. The last published standalone package remains v0.2.0.

## v0.2.1 acceptance

The accepted retail behavior is:

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

## Release model

Both ASI and standalone targets are built and validated from the same runtime. Public assets are edition-gated: an edition with an unresolved safety/distribution blocker may remain a CI-only validated artifact while another retail-accepted edition is released.

For v0.2.1, only the ASI ZIP and its public checksum are attached to the GitHub Release. The standalone ZIP remains inside CI validation only until #38 is resolved.

## Remaining work

Blocking standalone v0.2.1 distribution:

- resolve Defender issue #38 and record an independent/Microsoft false-positive verdict before publishing a new `version.dll` asset.

Compatibility debt:

- strict `WHGame.dll` fingerprint enforcement remains tracked in #36;
- revalidate ABI facts on any KCD2 update from 1.5.6.

Non-blocking follow-up:

- verify coexistence with additional real KCD2 ASI plugins; current support is for the tested loader/runtime path, not universal plugin combinations;
- investigate safe direct B resume only if a canonical vanilla mechanism is found;
- broader cutscene/dialogue and repeated-cycle/load-transition robustness;
- process-lifetime hook/hot-unload policy remains tracked separately.

## Decision rule

> Reuse vanilla KCD2 pause ownership, scope presentation changes to the real pause transition, and prefer a visible vanilla-menu fallback over unverified state manipulation.
