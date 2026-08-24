# Testing

This document describes the stable v0.1.0 smoke/compatibility test. Historical failed hypotheses are recorded in [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) and `RETAIL_EVIDENCE_*.md`.

## Supported test target

- KCD2 1.5.6 Windows retail;
- primary retail evidence: PC Xbox Store / Xbox app / Game Pass;
- Xbox controller first, with Escape analogous to Start/Menu.

## Install isolation

1. Close KCD2.
2. Remove/disable old `Documents\kingdomcome_mods\clean_pause` prototype PAKs.
3. Install only the release `version.dll` beside the game executable / `WHGame.dll`.
4. Do not overwrite another mod's unrelated `version.dll`.
5. Optionally delete the old `kcd2_clean_pause_native.log` before testing.

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
- vanilla pause depth-of-field blur is allowed.

### 3. Reveal vanilla menu

While Clean Paused, press Escape/Start again.

Expected: the already-open vanilla pause menu becomes visible with no intermediate gameplay tick.

Close it normally and confirm gameplay resumes.

### 4. B behavior

Enter Clean Pause again and press Xbox B.

Expected for **v0.1.0**: the ordinary vanilla pause menu becomes visible. This is intentional. B does not directly resume from Clean Pause.

Use normal KCD2 menu controls to resume.

### 5. Dialogue/subtitle

If naturally available in the same session:

- pause during a visible spoken subtitle;
- confirm the current subtitle remains visible during Clean Pause;
- confirm speech/audio/progression stop with the vanilla pause;
- reveal the normal menu with Start or B, then resume normally.

Do not create a separate game launch solely for a cutscene/subtitle edge case.

## Robustness

When convenient, exercise repeated pause cycles, load transitions, Alt-Tab, and controller reconnect. Any unresolved runtime assumption must degrade to ordinary visible vanilla pause rather than persistent input loss.

## CI

Repository CI also builds the x64 MSVC DLL, validates version-proxy exports/static runtime dependencies, and runs `tools/validate_native_contract.py` to enforce the production architecture.
