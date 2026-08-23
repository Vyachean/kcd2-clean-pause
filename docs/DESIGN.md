# Design

## Product requirement

Clean Pause exists for one reason: **pause KCD2 without obscuring the frame the player was looking at**.

This is especially useful for rereading subtitles, but the feature is global and should behave consistently during normal gameplay, dialogue, and in-engine cutscenes.

The visible result matters more than the specific mechanism used internally.

## Required state model

The implementation should be modelled explicitly rather than as a loose keybinding toggle.

### `Running`

The game is operating normally.

`Menu / Start` should be intercepted before the vanilla pause menu opens and transition to `CleanPaused`.

### `CleanPaused`

Requirements:

- game/dialogue/cutscene progression is stopped;
- renderer remains active enough to keep the current image visible;
- no pause overlay is opened;
- the current HUD/subtitle remains present where possible;
- controller input needed to leave this state remains functional.

Transitions:

- resume action -> `Running`;
- `Menu / Start` -> `VanillaMenu`.

### `VanillaMenu`

This is KCD2's own pause menu, not a clone or replacement.

Before handing control to the vanilla pause implementation, Clean Pause must relinquish any custom time-scale/freeze state so the engine does not accumulate two unrelated pause mechanisms.

What should happen after closing the vanilla menu is an explicit UX decision to test. The initial preference is to return to normal `Running` state rather than silently re-entering Clean Pause.

## Architecture

Keep three responsibilities separate.

### 1. Pause state controller

Owns only clean-pause state:

- captures the previous simulation/time-scale state;
- enters clean pause;
- resumes safely;
- performs cleanup if state becomes inconsistent;
- never owns controller mappings.

A promising first implementation is `t_scale 0`, because it can stop game simulation without inherently opening a UI. This remains a hypothesis until subtitle persistence is verified in the retail game.

### 2. Vanilla pause interceptor

Owns only the interception of the existing pause action.

Requirements:

- intercept the exact action KCD2 uses for normal pause/Menu;
- run before the vanilla pause UI opens;
- be able to consume/suppress that one invocation;
- leave all other vanilla controller actions unchanged;
- when Clean Pause is already active, deliberately invoke/forward to the original vanilla pause behaviour.

This is the critical unresolved implementation problem.

### 3. Vanilla menu bridge

Owns the transition from `CleanPaused` to KCD2's normal pause menu.

It must use the game's existing pause/menu implementation rather than reproducing `Menu.gfx` or building a custom menu.

## Implementation priority

Investigate solutions in this order:

1. **Existing KCD2 action/event hook** that can observe and consume the vanilla pause action before the UI handles it.
2. **Narrow declarative/static keybind patch** only if it can safely modify the relevant vanilla action without replacing unrelated bindings or user layouts.
3. **Small native input/action hook** only if retail Lua cannot consume the vanilla pause action safely.

A more complex implementation is acceptable if it produces a simpler and safer runtime contract. Avoid architectural simplicity that merely pushes conflicts onto the player.

## Forbidden approaches

Do not ship an implementation that does any of the following:

### `ActionMapManager.InitActionMaps()` from the mod

This clears/reinitializes existing action maps and device mappings. A prototype using it disabled Xbox-controller input even in the initial menu.

### Parallel binding on an already-used controller button without consuming vanilla behaviour

Examples already encountered:

- R3 also crouches / hard-locks;
- View/Back also invokes Skip Time;
- Menu/Start opens the normal pause menu;
- RB has a combat unlock action.

Adding another action does not solve the original interaction if the vanilla action still fires.

### Full replacement of `defaultProfile.xml`

Avoid copying and replacing the whole vanilla profile merely to change one action. It is fragile across game updates, conflicts with other mods, and risks breaking user controller layouts.

### Replacement of `Libs/UI/Menu.gfx`

Clean Pause should not become a custom pause-menu implementation. Replacing the entire menu is high-conflict and solves the wrong layer of the problem.

### External overlay/application

The goal is a native-feeling pause, not an OCR/subtitle companion application.

## Safety rules

- Failure to install an input hook must leave vanilla controls intact.
- No implementation may make the main menu dependent on the mod's custom action map.
- Resuming must restore the state captured on entry, not assume `t_scale == 1`.
- If the game is already paused/frozen by another mechanism, Clean Pause must not blindly claim ownership of that state.
- Input cleanup must be idempotent.
- A crash/reload cannot persist a broken controller mapping outside the running process.

## Compatibility target

First-class test target is the Windows PC build distributed through Xbox Store / Xbox app / Game Pass with an Xbox controller.

Do not assume Steam-only launch arguments, filesystem access, ASI loaders, or address libraries are available on that build.
