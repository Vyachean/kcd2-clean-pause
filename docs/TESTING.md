# Testing

This document describes the stable Clean Pause smoke/compatibility test. Historical failed hypotheses are recorded in [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) and `RETAIL_EVIDENCE_*.md`.

## Supported test target

- KCD2 1.5.6 Windows retail;
- primary retail evidence: PC Xbox Store / Xbox app / Game Pass;
- Xbox controller first, with Escape analogous to Start/Menu.

## Install isolation

Test exactly one Clean Pause edition at a time.

### Standalone edition

1. Close KCD2.
2. Remove/disable old `Documents\kingdomcome_mods\clean_pause` prototype PAKs and any Clean Pause ASI.
3. Install only the release `version.dll` beside the game executable / `WHGame.dll`.
4. Do not overwrite another mod's unrelated `version.dll`.
5. Optionally delete the old `kcd2_clean_pause_native.log` before testing.

### ASI edition

1. Close KCD2.
2. Remove the Clean Pause standalone `version.dll` edition.
3. Install one compatible x64 ASI loader, normally as `dinput8.dll` beside the game executable / `WHGame.dll`.
4. Install only `KCD2CleanPause.asi` beside that loader.
5. Do not overwrite an existing `dinput8.dll` blindly; preserve one compatible loader for all ASI plugins.
6. Optionally delete the old `kcd2_clean_pause_native.log` before testing.

The two Clean Pause editions should not be installed together. A process-wide guard prevents duplicate hooks if both are accidentally present, but dual installation is not a supported configuration.

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
- the retained game frame is not covered by the vanilla pause depth-of-field blur.

The implementation temporarily disables `wh_cl_NearDof` and `r_DepthOfField` only while Clean Pause owns presentation. It must preserve the values that were active before entering Clean Pause.

### 3. Reveal vanilla menu

While Clean Paused, press Escape/Start again.

Expected:

- the already-open vanilla pause menu becomes visible with no intermediate gameplay tick;
- the user's previous `wh_cl_NearDof` and `r_DepthOfField` values have been restored before normal menu presentation resumes;
- vanilla pause appearance is otherwise untouched.

Close it normally and confirm gameplay resumes with the same graphics behavior that existed before Clean Pause.

### 4. B behavior

Enter Clean Pause again and press Xbox B.

Expected under the current product contract: the ordinary vanilla pause menu becomes visible. B does not directly resume from Clean Pause. The pre-Clean-Pause DoF settings must be restored on this path too.

Use normal KCD2 menu controls to resume.

### 5. Dialogue/subtitle

If naturally available in the same session:

- pause during a visible spoken subtitle;
- confirm the current subtitle remains visible during Clean Pause;
- confirm the retained frame is sharp rather than inheriting the vanilla pause blur;
- confirm speech/audio/progression stop with the vanilla pause;
- reveal the normal menu with Start or B, then resume normally.

Do not create a separate game launch solely for a cutscene/subtitle edge case.

## Failure-path check

The blur suppression is part of the Clean Pause presentation contract, not an optional setting. If the runtime cannot safely access/save the DoF CVars, it must leave the ordinary visible vanilla pause menu rather than entering a partially working Clean Pause.

Any later fail-open path must attempt to restore the saved DoF values before returning presentation to vanilla. A transient restore failure remains retryable on subsequent input.

## ASI edition acceptance

The ASI package is a new loading path around the same runtime and requires one explicit retail-equivalence pass before stable release. Follow [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md).

After standalone ASI acceptance, test coexistence with at least one other real KCD2 ASI plugin loaded through the same ASI loader. This validates file-level coexistence and exercises hook ordering, but it does not imply universal compatibility with every native mod.

## Robustness

When convenient, exercise repeated pause cycles, load transitions, Alt-Tab, and controller reconnect. Any unresolved runtime assumption must degrade to ordinary visible vanilla pause rather than persistent input loss.

## CI

Repository CI builds both x64 MSVC native images, validates standalone version-proxy exports, validates both images as x64/static-runtime builds, and runs `tools/validate_native_contract.py` plus the dual-package contract tests.
