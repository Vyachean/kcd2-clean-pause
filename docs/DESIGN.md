# Design

## Product requirement

Clean Pause exists for one reason: **pause KCD2 without obscuring the frame the player was looking at**.

This is especially useful for rereading subtitles, but the feature is global and should behave consistently during normal gameplay, dialogue, and in-engine cutscenes.

The visible result matters more than the internal mechanism.

## Required state model

### `Running`

The game operates normally.

```text
Menu / Start -> CleanPaused
```

The vanilla pause overlay must not be rendered during this transition.

### `CleanPaused`

Requirements:

- game/dialogue/cutscene progression is stopped;
- current rendered image remains visible;
- no pause overlay/darkening/replacement screen is visible;
- current HUD/subtitle remains present where the game permits it;
- only the controller actions needed to leave Clean Pause remain active.

Transitions:

```text
B            -> Running
Menu / Start -> VanillaMenu
```

### `VanillaMenu`

This is KCD2's untouched pause menu, not a clone or replacement.

Clean Pause relinquishes native-pause ownership before handing off to the vanilla menu. Closing that menu returns to ordinary `Running` behavior rather than silently re-entering Clean Pause.

## Pause primitive

The current implementation uses:

```lua
Game.PauseGame(true)
Game.PauseGame(false)
```

rather than `t_scale 0`.

Reasons:

- it is KCD2/CryEngine's native pause primitive;
- it should stop more subsystems coherently than changing only simulation time scale;
- it does not require capturing/restoring arbitrary `t_scale` values;
- it separates **pausing the game** from **displaying the pause menu**.

The working product hypothesis is that the current subtitle can remain visible when the game is natively paused without starting the ingame menu. Retail testing is authoritative.

## Input architecture

### Exact vanilla action

KCD2 `player.lua` identifies:

```text
ui_start_pause
ui_back
```

The final UX should reuse the physical Menu/Start button rather than create a second global pause shortcut.

### Semantic interception, not physical-button replacement

A supplemental action map adds:

```text
clean_pause_start  -> xi_start
clean_pause_resume -> xi_b
```

An `actionFail` filter blocks only:

```text
ui_start_pause
```

CryEngine applies action filters before actions enter the dispatch priority list. Therefore in gameplay one physical Start press resolves as:

```text
physical xi_start
  |
  +-- ui_start_pause       -> filtered before vanilla UI listener
  |
  +-- clean_pause_start    -> CleanPause.StartPressed()
```

This is deliberately different from the discarded prototypes that put an additional action on an occupied controller button while allowing the vanilla action to fire too.

## Supplemental profile loading

The mod may add uniquely named action maps/filters through:

```lua
ActionMapManager.LoadFromXML(...)
```

It must never call:

```lua
ActionMapManager.InitActionMaps(...)
```

`LoadFromXML()` still mutates the action-map manager's current profile version. Therefore loading a guessed XML version is forbidden.

Bootstrap:

1. read effective `Libs/Config/defaultProfile.xml` with `System.LoadTextFile`;
2. parse the current root profile version;
3. load a supplemental profile only when an explicitly supported matching version exists;
4. verify the custom filters after loading;
5. otherwise leave vanilla controls unchanged.

The initial prototype supports only version `22`.

## Lifecycle-scoped interception

Blocking `ui_start_pause` globally would break Start behavior in the front-end or other UI contexts. The interceptor therefore follows runtime context.

A pause-aware timer monitor keeps the block enabled only where appropriate:

```text
front-end / no player -> vanilla pause action allowed
only_ui active        -> vanilla pause action allowed
running gameplay      -> vanilla pause action blocked
CleanPaused           -> vanilla pause action blocked
```

The supplemental custom action map can remain loaded; its commands are state-gated and harmless outside Clean Pause. The important mutation is the narrow vanilla-action filter, which is lifecycle-scoped.

If the player disappears while Clean Pause owns native pause, the implementation releases that pause and removes clean-pause isolation.

## Clean Pause input isolation

While clean-paused, an `actionPass` filter permits only:

```text
clean_pause_start
clean_pause_resume
```

This prevents ordinary gameplay actions from firing against the frozen simulation while keeping the two explicit exits usable.

Other KCD2 action filters can intersect with this filter. Dialogue/cutscene retail testing must prove that their active filter sets do not exclude the custom Start/B actions.

## Transitions

### Running -> CleanPaused

`clean_pause_start`:

1. verify gameplay interception is currently active;
2. enable/verify `clean_pause_only`;
3. call `Game.PauseGame(true)`;
4. mark Clean Pause ownership.

No vanilla menu API is invoked.

### CleanPaused -> Running

`clean_pause_resume`:

1. disable `clean_pause_only`;
2. call `Game.PauseGame(false)`;
3. clear Clean Pause ownership;
4. refresh gameplay interception.

### CleanPaused -> VanillaMenu

Second `clean_pause_start`:

1. disable `clean_pause_only`;
2. disable the `ui_start_pause` block so the real menu owns normal Start behavior;
3. call `Game.PauseGame(false)` to relinquish Clean Pause ownership;
4. invoke:

```lua
UIAction.CallFunction("MenuEvents", 0, "DisplayIngameMenu", true)
```

5. let KCD2's real menu enable its own `only_ui` filter and manage pause/unpause;
6. after the menu closes, the lifecycle monitor observes `only_ui == false` and restores gameplay interception.

No `Menu.gfx` replacement and no menu-close callback are required.

If the menu bridge fails, the transition rolls back to Clean Pause.

## Architecture boundaries

### Pause state controller

Owns only Clean Pause's native-pause state and safe transitions.

### Supplemental input adapter

Owns only:

- two custom semantic actions;
- one narrow vanilla-action block;
- one clean-pause allowlist filter;
- lifecycle scoping.

It must not become a general keybinding framework.

### Vanilla menu bridge

Owns only the explicit transition into KCD2's existing pause menu through `MenuEvents.DisplayIngameMenu(true)`.

It never draws or replaces UI.

## Forbidden approaches

### `ActionMapManager.InitActionMaps()`

Never call it. It clears/reinitializes existing action maps and controller/device mappings. A discarded prototype disabled Xbox-controller input globally, including the initial menu.

### Global `ui_start_pause` filtering

The vanilla pause action may be blocked only while Clean Pause intentionally owns gameplay Start semantics. Main/front-end and vanilla UI contexts must retain normal behavior.

### Parallel occupied-button binding without semantic suppression

A custom Start/R3/View/RB action is not sufficient if its vanilla semantic action is still dispatched.

### Full replacement of `defaultProfile.xml`

Too broad, fragile across updates, conflicts with other mods and user layouts.

### Replacement of `Libs/UI/Menu.gfx`

High-conflict and solves the wrong layer.

### External overlay/application

The goal is native-feeling pause, not a subtitle companion application.

## Safety rules

- Unsupported profile versions fail closed to vanilla behavior.
- Failure to verify supplemental filters must not enable the vanilla pause block.
- Main-menu controller navigation must not depend on Clean Pause.
- No persistent input configuration may be written.
- Cleanup must be idempotent.
- If native-pause acquisition fails, input isolation must be removed.
- If vanilla-menu handoff fails, restore Clean Pause atomically.
- A transition to no-player state must not leave Clean Pause's native pause owned.
- Never call a prototype released until Xbox Store retail testing proves zero overlay and subtitle persistence.

## Compatibility target

First-class target is the Windows PC build distributed through Xbox Store / Xbox app / Game Pass with an Xbox controller.

Do not assume Steam-only launch arguments, ASI loaders, address libraries, or writable game-install paths are available.
