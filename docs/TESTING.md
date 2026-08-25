# Testing

This document describes the current Clean Pause smoke/compatibility test. Historical failed hypotheses are recorded in [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) and `RETAIL_EVIDENCE_*.md`.

## Supported test target

- KCD2 1.5.6 Windows retail;
- primary retail evidence: PC Xbox Store / Xbox app / Game Pass;
- Xbox controller first, with Escape analogous to Start/Menu.

## Support status

- standalone `version.dll`: supported and retail-proven;
- `KCD2CleanPause.asi`: experimental until [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md) is completed.

ASI acceptance does **not** block the stable standalone `v0.2.0` release.

## Install isolation

Test exactly one Clean Pause edition at a time. A process-wide guard prevents duplicate hooks if both are accidentally present, but dual installation is unsupported.

### Standalone edition

1. Close KCD2.
2. Remove/disable old prototype PAKs and any Clean Pause ASI.
3. Install only the release `version.dll` beside the game executable / `WHGame.dll`.
4. Do not overwrite another mod's unrelated `version.dll`.

### ASI edition

1. Close KCD2.
2. Remove the Clean Pause standalone `version.dll` edition.
3. Install one compatible x64 ASI loader, normally as `dinput8.dll` beside the game executable / `WHGame.dll`.
4. Install only `KCD2CleanPause.asi` beside that loader.

## Core smoke test

### 1. Input safety

At the title menu and after loading a save, keyboard/mouse/controller navigation must remain normal.

### 2. Clean Pause

In exploration, press Escape or Xbox Start once.

Expected:

- no crash;
- world/simulation stops;
- audio pauses like ordinary KCD2 pause;
- the pause menu itself is not drawn;
- already-visible subtitle/HUD presentation remains visible where applicable;
- the retained frame is not covered by the vanilla pause depth-of-field blur.

### 3. Reveal vanilla menu / resume

While Clean Paused, press Escape/Start again or Xbox B.

Expected:

- the already-open vanilla pause menu becomes visible with no intermediate gameplay tick;
- the previous `wh_cl_NearDof` and `r_DepthOfField` values are restored before normal menu presentation;
- closing the menu resumes normal gameplay and graphics behavior.

The current standalone retail acceptance reports normal pause/menu/resume behavior after the `v0.2.0` subtitle/DoF changes. No additional dedicated launch is required for stable promotion.

### 4. Dialogue subtitle

When naturally available, pause during a visible dialogue subtitle and confirm that it remains visible while Clean Pause is active and that speech/audio/progression are paused coherently.

### 5. NPC overhead subtitle / speech bubble

While an NPC overhead chatter subtitle is visible, enter Clean Pause.

Expected:

- the exact existing overhead line remains visible;
- its text/anchor are not reconstructed by the mod;
- after revealing/closing the vanilla menu and resuming, KCD2 regains bubble ownership and subsequent overhead chatter behaves normally.

The overhead-bubble controller is optional/fail-open. Failure to discover `C_UIHudBubbles` must not break the core Clean Pause path.

## Failure paths

If the runtime cannot safely establish the core pause/HUD/DoF state, it must prefer the ordinary visible vanilla pause menu rather than leaving gameplay live with swallowed input.

## ASI follow-up

When an ASI tester is available, run [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md) and one coexistence case with another real KCD2 ASI plugin. Passing those checks promotes the ASI edition from experimental to supported; it is not required for standalone `v0.2.0` stability.

## Robustness

When convenient, exercise repeated pause cycles, load transitions, Alt-Tab, and controller reconnect. These are ongoing compatibility coverage, not blockers for the currently accepted standalone path.

## CI

Repository CI builds both x64 MSVC native images, validates standalone version-proxy exports, validates both images as x64/static-runtime builds, and runs the native, dual-package, blur-lifecycle, overhead-bubble, and versioning contract tests.
