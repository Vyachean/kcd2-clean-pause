# rc.5 diagnostic — retail Lua pause primitive

## Why rc.4 failed

Retail test of `v0.1.0-rc.4` produced a specific failure: after Escape or Xbox Start, the game continued running but stopped reacting to input.

The native implementation had two related defects:

1. `SSystemGlobalEnvironment + 0x98` was treated as `IGameFramework*`. Current KCD2 1.5.6 reverse engineering identifies that field as `IGame*` (`wh::game::C_Game`). Its vtable slot 13 is `GetName()` and returns `"kcd2"`; it is not `PauseGame`.
2. `SetNativePause()` treated "the inferred vfunc returned without an access violation" as proof that pausing succeeded. It then set `g_cleanPaused=true`, causing the input hook to consume gameplay/dialogue input even though the game had not paused.

The rc.4 direct native pause ABI is therefore rejected and guarded against in CI.

## Why rc.5 uses a Lua probe

Warhorse ScriptBind documentation exposes:

```lua
Action.PauseGame(pause)
```

and describes it as putting the game into or out of pause mode. A captured KCD2 retail Lua global-state dump also lists `PauseGame()` under `CryAction`.

The earlier rc.3 diagnostic tested only `Game.PauseGame`, which the tested Xbox Store 1.5.6 runtime did not expose. It did not test `CryAction.PauseGame` or `Action.PauseGame`.

## rc.5 safety contract

rc.5 is deliberately diagnostic:

- Escape is always forwarded untouched.
- Xbox Start is always forwarded untouched.
- No `g_cleanPaused` state exists.
- No `IGameFramework` pause vfunc is called.
- F10 is the only intercepted key.
- F10 probes, in order:
  1. `CryAction.PauseGame(bool)`
  2. `Action.PauseGame(bool)`
  3. `Game.PauseGame(bool)`
- a second F10 requests resume if the first Lua call completed successfully.
- failure never changes routing for any other input.

The native log records the selected Lua route and `pcall` result.

## Acceptance gate

Do not restore Start/Escape interception until a retail test proves that one of the Lua pause bindings actually freezes gameplay/dialogue without showing the pause menu and resumes cleanly.
