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
- do not rely on a supplemental runtime Start map; it failed to intercept Start in two retail tests;
- do not require a full `defaultProfile.xml` replacement for the active native implementation.

## rc3 proved the Lua command chain

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
5. failure occurs specifically at the requested Lua pause primitive.

F10 appearing to do nothing visually was **not** an input-routing failure.

## Correction: `Game.PauseGame` is not a usable retail Lua API

Earlier documentation treated generated ScriptBind method lists as proof that `Game.PauseGame` was callable in retail. The rc3 log falsifies that assumption.

Independent export data strengthens the runtime result:

- the retail Lua-closure dump contains no `PauseGame` closure;
- the crossmatch lists `CryAction.PauseGame` as `kcdrewrite_only`, not retail.

Accordingly, the project must not ship another pure-profile/Lua candidate that depends on `Game.PauseGame`.

## Confirmed native pause primitive

Reverse engineering for **WHGame.dll 1.5.6** identifies the KCD2 `IGameFramework` / `CCryAction` vtable and maps slot 13 to the game-framework pause method. The matching CryAction interface signature is:

```cpp
PauseGame(bool pause, bool force, unsigned int fadeOutInMs)
```

The active native candidate therefore calls slot 13 directly as:

```text
IGameFramework::PauseGame(paused, true, 0)
```

The runtime does not use a fixed Xbox-Store address for `pGameFramework`: it locates `SSystemGlobalEnvironment`, validates its ScriptSystem/Input/System objects, and now additionally requires the slot-13 target to be executable before installing the input hook.

If that validation fails, no hook is installed and KCD2 keeps vanilla input.

## Native input architecture

The existing narrow native prototype hooks `IInput::PostInputEvent` before `ActionMapManager`.

Running:

```text
Escape / Xbox Start press
  -> read-only Lua eligibility check (player exists; only_ui is false)
  -> direct native PauseGame(true, true, 0)
  -> consume physical press before vanilla pause action
```

Clean Paused:

```text
B
  -> native PauseGame(false, true, 0)
  -> consume B press/release

Escape / Start
  -> call MenuEvents.DisplayIngameMenu(true)
  -> verify only_ui became active
  -> leave native pause active during handoff
```

All other KCD2 input events are consumed while Clean Pause owns the pause state.

Lua is no longer responsible for pausing. It is used only for read-only context checks and the UI handoff because those retail APIs were independently observed/available.

## Remaining retail questions

The next native prerelease must establish:

1. whether the `version.dll` proxy loads on this exact Microsoft Store installation;
2. whether runtime environment / slot-13 validation succeeds;
3. whether first Escape/Start freezes the game without a vanilla-menu frame;
4. whether current HUD/subtitle remains visible;
5. whether dialogue audio and in-engine cutscene progression stop coherently;
6. whether B resumes without leaking an underlying action;
7. whether unrelated input is inert while paused;
8. whether `MenuEvents.DisplayIngameMenu(true)` successfully performs second-Start handoff without an intermediate unpause;
9. whether repeated pause/resume, loading, death, Alt-Tab and controller reconnect leave no stuck state.

These cannot be established by CI; CI only proves compilation, packaging and static ABI/safety contracts.
