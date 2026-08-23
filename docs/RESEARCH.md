# Research notes

This file records findings that constrain implementation decisions. Confirmed behaviour is kept separate from retail hypotheses.

## Confirmed KCD2 findings

### Lua mod bootstrap

KCD2 supports Lua mod entry points under:

```text
Scripts/Mods/<modid>.lua
```

inside a mod `.pak`.

### Exact player pause/back actions

Current KCD2 `Scripts/Scripts/Entities/actor/player.lua` contains:

```lua
function Player:OnAction(action, activation, value)
    -- called by engine when some action happen
    -- for now got just ui_back, ui_start_pause
```

Therefore the relevant action names are confirmed:

- `ui_start_pause` — normal Menu / Start pause action;
- `ui_back` — UI back action.

This makes a runtime wrapper around `Player.OnAction` a useful observation point without inventing a new controller binding.

Source:

- https://github.com/muyuanjin/kcd2-mod-docs/blob/main/Scripts/Scripts/Entities/actor/player.lua

### Native game pause exists

KCD2's Lua API exposes:

```lua
Game.PauseGame(...)
```

and KCD2's own `SinglePlayer.lua` calls:

```lua
Game.PauseGame(true)
```

This is now the preferred clean-pause primitive to test before `t_scale 0`.

Sources:

- https://github.com/Jefferson25625/kcd2-exports/blob/main/KCD2_LuaAPI_Reference.md
- https://github.com/muyuanjin/kcd2-mod-docs/blob/main/Scripts/Scripts/GameRules/SinglePlayer.lua

### FlashUI can call UI event systems from Lua

KCD2 exposes `UIAction.CallFunction`. CryEngine's implementation first attempts a UI element and then, if no element matches, looks up a UI-to-system event system by the same name and synchronously sends the requested event.

Conceptually:

```lua
UIAction.CallFunction(eventSystemName, 0, eventName, ...)
```

Source API docs:

- https://github.com/muyuanjin/kcd2-mod-docs/blob/main/script_bind_2025_01_14/!!MEMBERTYPE_Methods_CScriptBindUIAction.html

Reference implementation:

- https://github.com/MergHQ/CRYENGINE/blob/release/Code/CryEngine/CryAction/FlashUI/ScriptBind_UIAction.cpp

### `ActionMapManager.EnableActionFilter` is exposed

KCD2 script-bind documentation includes:

```lua
ActionMapManager.EnableActionFilter(name, enabled)
```

The prototype uses the already-existing `only_ui` filter rather than modifying any bindings.

Source:

- https://github.com/muyuanjin/kcd2-mod-docs/blob/main/script_bind_2025_01_14/CScriptBind_ActionMapManager__EnableActionFilter@IFunctionHandler_@char_@bool.html

### `ActionMapManager.InitActionMaps()` is unsafe for this use

CryEngine's `InitActionMaps(path)` clears existing action maps, filters, controller layouts and input-device mappings before loading the supplied file.

A previous Clean Pause prototype invoked it with a profile containing only the mod action map.

**Observed result on the target game:** all Xbox-controller input stopped working, including the initial menu.

Permanent constraint:

> Clean Pause must never call `ActionMapManager.InitActionMaps()`.

Reference implementation:

- https://github.com/MibuWolf/CryGame/blob/master/Code/CryEngine/CryAction/ActionMapManager.cpp

### `LoadFromXML()` does not solve physical-button conflicts by itself

`ActionMapManager.LoadFromXML()` can add uniquely named action maps without the global reset performed by `InitActionMaps()`.

However, adding a second action to a physical button does not remove the existing KCD2 action. Earlier R3/View/RB experiments therefore produced double-action/conflict problems.

### There is no useful free standard Xbox button

Observed/known conflicts include:

- R3: crouch / hard lock;
- View/Back: Skip Time;
- Menu/Start: vanilla pause menu;
- RB: combat unlock;
- remaining normal controls already serve gameplay/UI functions.

The final UX should reuse the game's own pause action rather than invent a global extra shortcut.

## Confirmed CryEngine pause-menu architecture relevant to KCD2

The following is confirmed from CryEngine reference source. KCD2 clearly retains related concepts (`ui_start_pause`, FlashUI, the action-map APIs), but the exact runtime event-system name still requires testing on the retail build.

### UI input handles `ui_start_pause`

CryEngine `CUIInput` registers:

```cpp
ADD_HANDLER(ui_start_pause, OnActionStartPause);
```

and its pause handler opens the ingame menu via:

```cpp
pMenuEvents->DisplayIngameMenu(true);
```

`CUIInput` is registered as an `IBlockingActionListener` / "always" action listener.

Source:

- https://github.com/MergHQ/CRYENGINE/blob/release/Code/GameSDK/GameDll/UI/UIInput.cpp

### Blocking always listeners run before normal listeners

`CActionMapManager::HandleAcceptedEvents` processes always listeners first. If one reports the action handled, later normal action listeners are skipped for that delivery path.

This means `Player.OnAction` must not be assumed to be a pre-consumption hook simply because KCD2 documents `ui_start_pause` there. Retail ordering must be observed.

Source:

- https://github.com/MibuWolf/CryGame/blob/master/Code/CryEngine/CryAction/ActionMapManager.cpp

### Vanilla menu pause and menu UI are separable

CryEngine `CUIMenuEvents` exposes a UI-to-system event system named:

```text
MenuEvents
```

with:

```text
DisplayIngameMenu(bool)
```

Opening the menu:

1. sets the ingame-menu state;
2. calls native `PauseGame(true, true)`;
3. enables the existing `only_ui` filter;
4. emits the UI event that displays the menu.

Closing the menu:

1. calls `PauseGame(false, true)`;
2. disables `only_ui`;
3. emits the UI event that hides the menu.

Reference source:

- https://github.com/MergHQ/CRYENGINE/blob/release/Code/GameSDK/GameDll/UI/UIMenuEvents.cpp

This separation is the key to the new prototype: ask the real menu subsystem to close, then immediately acquire native pause without emitting a menu-start event.

## Current implementation hypothesis: same-cycle menu cancellation

The repository prototype now tests this flow:

```text
Running
  |
  | Menu / Start -> ui_start_pause
  v
vanilla pause handling
  |
  v
Player.OnAction observer
  |
  +-> UIAction.CallFunction("MenuEvents", 0, "DisplayIngameMenu", false)
  |
  +-> Game.PauseGame(true)
  |
  +-> enable existing "only_ui" filter
  v
CleanPaused, no menu UI
```

Resume:

```text
ui_back
  -> disable only_ui
  -> Game.PauseGame(false)
  -> Running
```

Vanilla-menu handoff:

```text
CleanPaused + ui_start_pause
  -> UIAction.CallFunction("MenuEvents", 0, "DisplayIngameMenu", true)
  -> vanilla menu owns pause lifecycle
```

No controller binding is added or replaced.

## Why this is worth testing before a native hook

If `Player.OnAction` occurs after the vanilla UI handler but before rendering, the menu can potentially be opened and closed inside a single input/update cycle and never appear on screen.

It also avoids the largest compatibility risks:

- no controller remapping;
- no full `defaultProfile.xml` patch;
- no `Menu.gfx` replacement;
- no ASI loader;
- no storefront-specific address library.

### Fail-safe behaviour

If `UIAction.CallFunction("MenuEvents", ...)` does not resolve on retail KCD2, the prototype refuses to acquire Clean Pause. The vanilla menu remains authoritative.

If native pause acquisition fails after hiding the menu, the prototype asks the vanilla menu to open again.

Neither failure path changes persistent controller configuration.

## Important unresolved ordering case

A possible failure sequence is:

```text
Player.OnAction first
  -> DisplayIngameMenu(false) sees nothing open
  -> Clean Pause acquires native pause
  -> later vanilla CUIInput opens the menu
```

This would leave controls safe but fail the visual requirement.

If retail testing shows this ordering, next pure-Lua experiment:

- use `Script.SetTimer(0, callback, userData, true)` as a pause-aware deferred finalizer;
- close the vanilla menu after the input pipeline has completed;
- measure whether it still happens before a rendered frame.

KCD2 script-bind docs explicitly support timers that update during pause.

If even a zero-delay finalizer produces a visible one-frame menu flash, pure Lua is insufficient for the strict goal and the next step is a **narrow native blocking-action hook for `ui_start_pause`**, not controller remapping.

## `SimulateOnAction` cannot drive the vanilla UI path

KCD2 exposes `Actor.SimulateOnAction`, but CryEngine's implementation directly invokes:

```cpp
pActor->OnAction(action, mode, value);
```

It bypasses `ActionMapManager` and therefore bypasses the UI blocking listener that handles normal menu input.

So this is **not** a valid way to synthesize `ui_back` into the vanilla menu.

Sources:

- https://github.com/muyuanjin/kcd2-mod-docs/blob/main/script_bind_2025_01_14/C_ScriptBindActor__SimulateOnAction@IFunctionHandler__@char__@int@float.html
- https://github.com/CryDevPortal/CryGame/blob/master/Game/GameDll/ScriptBind_Actor.cpp

## `t_scale` remains a fallback, not the preferred primitive

KCD2 exposes `t_scale`, and speed-control mods demonstrate that it affects in-engine cutscenes.

It remains useful if native `Game.PauseGame(true)` proves to hide subtitles or fails to pause a target scene type. But native pause should be tested first because it is more likely to stop audio, dialogue and engine subsystems coherently.

## Full pause-menu replacement remains rejected

Replacing `Libs/UI/Menu.gfx` is high-conflict and unnecessary if the existing menu event system can be bridged. Clean Pause should invoke the vanilla menu deliberately, not own a fork of it.

## Discarded prototypes

No prototype ZIP created before this repository is a release.

### 0.2 / 0.3

Long-press bindings; vanilla actions on the same physical buttons still fired.

### 0.4

Called `InitActionMaps()` with a custom profile.

**Result:** controller disabled globally.

**Never reuse this design.**

### 0.5

Used safer `LoadFromXML()` plus RB, but still solved the wrong problem by searching for an alternative physical button.

## Retail questions that remain

1. Does Xbox Store KCD2 expose `MenuEvents.DisplayIngameMenu` under exactly that name?
2. Does `Player.OnAction` observe `ui_start_pause` in the retail input ordering used by the current build?
3. Does the first Start result in **zero visible menu flash**?
4. Does `Game.PauseGame(true)` leave the current rendered frame and subtitle visible?
5. Does it stop dialogue audio and cutscene progression coherently?
6. Does `ui_back` reach the Player hook while `only_ui` is enabled so B can resume?
7. Does second Start cleanly open and hand control to the normal pause menu?
8. What happens in prerendered videos?
9. Do loading/death/save transitions require explicit recovery hooks?

## Evidence required from retail testing

Record:

- exact KCD2 version/storefront;
- `[Clean Pause]` lines from `kcd.log`;
- whether `ui_start_pause` and `ui_back` were observed;
- whether any vanilla menu frame became visible;
- subtitle persistence;
- audio behaviour;
- resume behaviour;
- vanilla-menu handoff;
- controller behaviour after returning to main menu.
