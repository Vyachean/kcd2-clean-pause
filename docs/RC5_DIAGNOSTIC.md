# rc.5 diagnostic — historical result

> **Status: complete / superseded.** This document records why rc.5 existed and what the retail test proved. The active architecture and next steps are in [STATUS_AND_PLAN.md](STATUS_AND_PLAN.md).

## Why rc.5 existed

`v0.1.0-rc.4` failed after Escape/Xbox Start: gameplay continued but ordinary input became unresponsive.

The root cause was an invalid native ABI assumption:

1. `SSystemGlobalEnvironment + 0x98` was treated as `IGameFramework*`, but current KCD2 1.5.6 reverse engineering identifies it as `IGame*` (`wh::game::C_Game`).
2. KCD2 `IGame` slot 13 is `GetName()` (`"kcd2"`), not PauseGame.
3. rc.4 considered the inferred call successful merely because it returned without an access violation, then set its own `g_cleanPaused=true` and swallowed input although the game had not paused.

rc.5 therefore removed the inferred native PauseGame call and removed Start/Escape interception entirely.

## Diagnostic safety contract

rc.5 was intentionally not a production candidate:

- Escape was always forwarded untouched;
- Xbox Start was always forwarded untouched;
- no persistent input-swallow state existed;
- no inferred `IGameFramework::PauseGame` vfunc was called;
- F10 was the only intercepted key;
- F10 probed the retail Lua pause bindings;
- failure could not disable normal vanilla pause/input.

## Retail result

The retail test established that a Lua pause binding can freeze **world simulation**.

That was useful, but insufficient for Clean Pause. The diagnostic did not reproduce the complete vanilla KCD2 pause lifecycle:

- audio/UI continued;
- subtitle lifetime was not retained correctly;
- the result was a partial simulation freeze rather than the coherent pause state required by the product contract.

Therefore the important conclusion is:

> `PauseGame` can stop simulation, but custom pause ownership does not automatically reproduce vanilla pause behavior across audio, UI, dialogue/cutscene state and subtitle presentation.

## Decision

The following are rejected as the production pause mechanism:

```text
CryAction.PauseGame(...)
Action.PauseGame(...)
Game.PauseGame(...)
inferred native IGameFramework::PauseGame(...)
```

The next architecture instead lets KCD2 execute its ordinary pause path and hides only the visible pause-menu presentation after vanilla pause ownership is verified.

See:

- [DESIGN.md](DESIGN.md)
- [RESEARCH.md](RESEARCH.md)
- [STATUS_AND_PLAN.md](STATUS_AND_PLAN.md)
- [TESTING.md](TESTING.md)
