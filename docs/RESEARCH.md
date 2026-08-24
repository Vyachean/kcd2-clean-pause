# Research notes

Confirmed facts are separated from runtime questions that still need Xbox Store 1.5.6 testing.

## Retail input/profile findings

The exact Xbox Store 1.5.6 `defaultProfile.xml` uses:

```text
ordinary gameplay        open_menu/open_menu
dialogue/cutscene/etc.   open_pause_menu/open_pause_menu
```

with retail Escape/keybind and Xbox `xi_start` bindings.

`rc.1` and `rc.2` proved that replacing/splitting these vanilla actions is unsafe. `rc.3` restored the originals completely and normal Escape/Start pause returned.

Permanent rules:

- do not call `ActionMapManager.InitActionMaps()`; a previous prototype disabled controller input globally;
- do not rely on a supplemental runtime Start map; it failed to intercept Start in retail testing;
- do not require a full `defaultProfile.xml` replacement for the active native diagnostic implementation.

## rc.3 proved the Lua command chain — but only tested Game.PauseGame

`v0.1.0-rc.3` used a separate keyboard-only F10 `consoleCMD` probe while leaving vanilla Escape/Start untouched.

Retail log on Xbox Store 1.5.6 contains:

```text
Loading lua init script for mod clean_pause ...
[Clean Pause] official runtime loaded; routed actions=clean_pause_probe_gameplay,clean_pause_probe_pause_context
...
[Clean Pause] Game.PauseGame unavailable
```

Therefore the following are confirmed on the target retail build:

1. the mod PAK loads;
2. `Scripts/Mods/clean_pause.lua` executes;
3. `System.AddCCommand` registration works;
4. the F10 profile `consoleCMD` reaches the registered command;
5. that specific probe fails because `Game.PauseGame` is not present.

F10 appearing to do nothing visually was **not** an input-routing failure.

The previous project conclusion — "retail Lua has no pause primitive" — was too broad. The rc.3 test did not check the `CryAction` or `Action` tables.

## Lua pause bindings worth testing

Warhorse ScriptBind documentation contains `CScriptBindAction::PauseGame(IFunctionHandler*, bool)` and documents its Lua syntax as:

```lua
Action.PauseGame(pause)
```

with the description "Puts the game into pause mode" and `true`/`false` for pause/resume.

A captured KCD2 Lua global-state dump separately lists:

```text
CryAction = {
  ...
  PauseGame()
  ...
}
```

Accordingly, `rc.5` probes the target retail runtime in this order:

1. `CryAction.PauseGame(bool)`;
2. `Action.PauseGame(bool)`;
3. legacy `Game.PauseGame(bool)`.

No Start/Escape interception is enabled while this is unresolved.

## rc.4 native failure — corrected ABI facts

`v0.1.0-rc.4` attempted to bypass Lua and call an inferred `IGameFramework::PauseGame` vfunc directly.

Retail result:

- Escape/Start were intercepted;
- the simulation did not pause;
- ordinary input then became unresponsive.

The implementation error is now identified precisely.

### gEnv +0x98 is IGame*, not IGameFramework*

Current KCD2 1.5.6 reverse engineering of `SSystemGlobalEnvironment` verifies:

```cpp
Offsets::IGame* pGame; // +0x98
```

The KCD2 `IGame` vtable verifies:

```text
slot 12 -> GetLongName() -> "Kingdom Come: Deliverance"
slot 13 -> GetName()     -> "kcd2"
```

rc.4 treated the +0x98 pointer as `IGameFramework*` and called slot 13 through a PauseGame-shaped function pointer. In practice that meant calling `IGame::GetName()` with extra arguments. Windows x64 calling convention allowed that call to return without an access violation, so the code falsely treated it as successful pause acquisition.

### rc.4 had no pause-state confirmation

`SetNativePause()` returned success when the inferred call merely did not throw a structured exception. It did not verify that KCD2 actually entered a paused state.

The hook then set `g_cleanPaused=true` and consumed underlying gameplay/dialogue input. That exactly explains the retail symptom: the world kept running while controls appeared dead.

### IGameFramework slot 13 is not a proven KCD2 callable contract

The latest reverse-engineered `IGameFramework` table annotates slot 13 as a 618-byte function corresponding to **KCD1 PauseGame**, but its exact KCD2 signature is not established. A KCD2 `I_UIMenu` callsite invokes framework `+0x68` (slot 13) with four explicit arguments and checks adjacent slot 14 with a `uint16_t id`, which already differs from the stock CryEngine signature rc.4 assumed.

Therefore the project must not call slot 13 again until the exact KCD2 ABI, reason/id and state semantics are independently established.

CI now rejects the old `kGameFrameworkPauseGameSlot`, `PauseGameFn`, `g_gameFramework`, `SetNativePause` and persistent `g_cleanPaused` contract.

## rc.5 diagnostic architecture

The native `version.dll` still uses the proven raw `IInput::PostInputEvent` hook and runtime gEnv locator, but only for a safe F10 diagnostic.

The locator now models +0x98 correctly as `IGame*` and uses `IGame` slots 12/13 only as executable structural anchors; it never invokes them.

Input behavior:

```text
Escape / Xbox Start / every non-F10 input
  -> always forward directly to KCD2

F10 press in gameplay
  -> read-only context check
  -> probe CryAction.PauseGame / Action.PauseGame / Game.PauseGame
  -> log route + pcall result

second F10 after a successful Lua call
  -> request resume through the same discovery order
```

There is no global input-swallow mode in rc.5. Even if a Lua pause binding is absent or unexpectedly ineffective, normal Start/Escape and all unrelated controls remain vanilla.

## Remaining retail questions

The next retail test must establish only a narrow set of facts:

1. Escape remains ordinary vanilla pause under rc.5;
2. Xbox Start remains ordinary vanilla pause under rc.5;
3. which Lua pause binding, if any, exists on Xbox Store 1.5.6;
4. whether F10 through that binding actually freezes world simulation;
5. whether dialogue/cutscene audio/progression freezes coherently;
6. whether current HUD/subtitle remains visible;
7. whether a second F10 resumes cleanly.

Only after those points are proven should Start/Escape interception, B resume and second-Start vanilla-menu handoff be restored.

Compilation/CI cannot establish the actual runtime pause effect; it can only prove the fail-open input contract, Windows build, packaging and known ABI guards.
