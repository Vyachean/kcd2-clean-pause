# Design

## Product requirement

Clean Pause exists for one reason: **pause KCD2 without obscuring the frame the player was looking at**.

This is especially useful for rereading subtitles, but the feature is global and should behave consistently during normal gameplay, dialogue, and in-engine cutscenes.

The visible result matters more than the specific mechanism used internally.

## Required state model

### `Running`

The game is operating normally.

Preferred transition:

```text
Menu / Start -> CleanPaused
```

The player must not be left looking at the vanilla pause overlay during this transition.

### `CleanPaused`

Requirements:

- game/dialogue/cutscene progression is stopped;
- renderer remains active enough to keep the current image visible;
- no pause overlay is visible;
- the current HUD/subtitle remains present where the game permits it;
- controller input needed to leave this state remains functional.

Transitions:

```text
B / ui_back    -> Running
Menu / Start   -> VanillaMenu
```

### `VanillaMenu`

This is KCD2's own pause menu, not a clone or replacement.

Clean Pause relinquishes ownership once the vanilla menu accepts the handoff. Closing the vanilla menu should resume ordinary gameplay rather than silently re-enter Clean Pause.

## Current preferred architecture

Research changed the preferred pause primitive. `t_scale 0` remains useful evidence that rendering can continue while simulation is stopped, but the prototype now uses **KCD2's native `Game.PauseGame(true)`**.

Reasons:

- it is the engine's real pause mechanism;
- it should stop more subsystems coherently than only changing simulation time scale;
- it avoids having to capture and restore an arbitrary `t_scale` value;
- it is already used by KCD2 game scripts;
- the pause menu and the act of pausing can be treated as separate concerns.

The working hypothesis is that subtitles disappear during the normal pause experience because the ingame menu/UI state replaces or hides them, not because native game pause inherently requires the overlay. Retail testing must prove this.

## Input/menu strategy: reuse the vanilla action, do not remap it

Current KCD2 `player.lua` documents the relevant actions as:

- `ui_start_pause` — Menu / Start;
- `ui_back` — Back / B UI action.

The prototype wraps `Player.OnAction` at runtime. It does **not** replace `player.lua`, alter `defaultProfile.xml`, or add a second binding to the physical Menu button.

### First Menu / Start press

The normal KCD2/CryEngine flow opens the ingame menu. Clean Pause observes `ui_start_pause` and attempts a same-input-cycle transformation:

```text
vanilla ui_start_pause
        |
        v
vanilla menu starts / attempts to start
        |
        v
MenuEvents.DisplayIngameMenu(false)
        |
        +-- hides/stops vanilla ingame menu
        +-- relinquishes vanilla menu pause/filter state
        |
        v
Game.PauseGame(true)
        |
        v
CleanPaused (no menu UI)
```

The bridge call is made through the existing FlashUI script API:

```lua
UIAction.CallFunction("MenuEvents", 0, "DisplayIngameMenu", false)
```

`UIAction.CallFunction` can dispatch functions to a UI-to-system event system, so no `Menu.gfx` replacement is needed.

### Resume with B

While Clean Pause owns the pause state:

```text
ui_back -> Game.PauseGame(false) -> Running
```

The prototype also uses KCD2's existing `only_ui` filter while clean-paused, matching the input isolation used by the vanilla ingame menu without changing any binding.

### Second Menu / Start press

While clean-paused, Menu / Start deliberately transfers ownership to the real menu:

```lua
UIAction.CallFunction("MenuEvents", 0, "DisplayIngameMenu", true)
```

The vanilla menu then owns pause/unpause and UI filtering until it closes.

## Why this is fail-safer than the old controller prototypes

The current prototype:

- installs no controller map;
- calls no `InitActionMaps`;
- changes no persistent user/controller configuration;
- adds no parallel action to R3/View/RB/Menu;
- leaves the initial/front-end menu untouched because the hook lives on the in-game Player action path;
- refuses to take clean-pause ownership if the `MenuEvents` bridge cannot be called.

If the retail KCD2 build does not expose `MenuEvents.DisplayIngameMenu`, the expected failure is simply ordinary vanilla pause behaviour plus a log entry — not broken controller input.

## Critical unresolved ordering question

The exact retail ordering between KCD2's UI input listener and `Player.OnAction` must be measured.

Two acceptable cases exist:

1. vanilla menu handling occurs before `Player.OnAction`: the synchronous `DisplayIngameMenu(false)` call can close it in the same input cycle;
2. the game has already been modified by Warhorse so `ui_start_pause` reaches Player early enough and the bridge still prevents any rendered overlay.

A problematic case is:

- `Player.OnAction` runs first;
- the prototype closes a menu that is not open yet;
- the vanilla UI listener opens it after the Lua hook returns.

That case is safe for controller state but fails the visual goal. If observed, the next experiment is a pause-aware zero-delay `Script.SetTimer(..., true)` finalizer, or a narrower native blocking-action hook. Do not solve it by remapping Menu/Start.

## Architecture boundaries

### Pause state controller

Owns only whether Clean Pause itself owns native game pause.

### Player action observer

Observes `ui_start_pause` / `ui_back` while preserving the original `Player.OnAction` implementation.

It must never become a general-purpose input framework.

### Vanilla menu bridge

Owns only:

```text
MenuEvents.DisplayIngameMenu(false/true)
```

It never draws or replaces the menu.

## Forbidden approaches

### `ActionMapManager.InitActionMaps()`

Never call it from this mod. It clears/reinitializes existing action maps and controller/device mappings. A previous prototype disabled Xbox-controller input globally, including the initial menu.

### Parallel binding on an already-used controller button

Do not add another Menu/R3/View/RB binding while leaving vanilla behaviour active.

### Full replacement of `defaultProfile.xml`

Too broad and fragile for changing one interaction.

### Replacement of `Libs/UI/Menu.gfx`

High-conflict and solves the wrong layer.

### External overlay/application

The goal is native-feeling pause, not a subtitle companion application.

## Safety rules

- Failure of the bridge/hook must preserve vanilla controls.
- Main-menu controller navigation must not depend on Clean Pause code.
- Clean Pause must not persist any input configuration.
- Cleanup must be idempotent.
- If clean-pause acquisition fails after hiding the vanilla menu, restore the vanilla menu immediately.
- Never report the implementation as released until retail Xbox Store testing proves subtitle persistence and zero visible menu flash.

## Compatibility target

First-class test target is the Windows PC build distributed through Xbox Store / Xbox app / Game Pass with an Xbox controller.

Do not assume Steam-only launch arguments, ASI loaders, address libraries, or writable game-install paths are available.
