# Deterministic action-filter prototype

This branch implements the preferred controller architecture. It replaces the earlier timing-dependent `Player.OnAction`/menu-cancellation experiment.

## Why this approach

CryEngine evaluates action filters before an action is added to the dispatch priority list. An `actionFail` filter containing only `ui_start_pause` can therefore suppress KCD2's vanilla pause action before the UI listener sees it, while a custom action on the same physical Xbox Menu/Start button still runs because it has a different action ID.

```text
physical xi_start
  |
  +-- ui_start_pause       -- filtered before dispatch
  |
  +-- clean_pause_start    -- allowed -> CleanPause.StartPressed()
```

There is no menu-open/menu-close race and no need for a spare controller button.

## Packaged profile

`src/Libs/Config/cleanPauseProfile_v22.xml` defines:

- `clean_pause_controls`
  - `clean_pause_start` -> `xi_start`
  - `clean_pause_resume` -> `xi_b`
- `clean_pause_block_vanilla_pause` (`actionFail`)
  - blocks only `ui_start_pause`
- `clean_pause_only` (`actionPass`)
  - permits only the two Clean Pause actions while clean-paused

The build validator checks this contract structurally rather than treating the XML as opaque data.

## Version-safe loading

`ActionMapManager.LoadFromXML()` changes the action-map manager's in-memory version to the supplemental XML root version. Loading a guessed version is therefore unsafe.

The prototype does not ask the user to supply this value. At runtime it:

1. reads the effective `Libs/Config/defaultProfile.xml` through `System.LoadTextFile`;
2. extracts its root profile version;
3. loads `cleanPauseProfile_v22.xml` only when the detected version is exactly `22`;
4. otherwise leaves vanilla controls untouched and logs the reason.

The supported-version check happens **before** `LoadFromXML()`.

## Partial-load safety

The Lua binding for `LoadFromXML()` does not return the underlying C++ success value. The bootstrap therefore performs additional checks:

- confirms the packaged profile is readable before loading it;
- statically validates the action-map/action schema at build time;
- loads the profile;
- proves both custom filters exist by enabling them and querying `IsFilterEnabled()`;
- leaves both filters disabled until initialization is complete.

No code path calls `InitActionMaps()`.

## Lifecycle-scoped interception

The vanilla Start action is **not blocked globally**.

A pause-aware `Script.SetTimer` monitor keeps the interception state synchronized with game context:

```text
no gameplay player        -> vanilla ui_start_pause allowed
only_ui enabled           -> vanilla ui_start_pause allowed
active gameplay           -> vanilla ui_start_pause blocked
Clean Pause               -> vanilla ui_start_pause blocked
```

This matters for the front-end/main menu and for KCD2's own UI. Loading the mod must not make Menu/Start unusable outside gameplay.

If the player disappears while Clean Pause owns native pause, the monitor performs recovery: removes clean-pause input isolation, resumes native pause, and drops interception.

## Runtime states

### Running gameplay

- custom controller map enabled;
- `clean_pause_block_vanilla_pause` enabled;
- `clean_pause_only` disabled.

Start therefore invokes `clean_pause_start` without the vanilla pause menu receiving `ui_start_pause`.

The custom B action is harmless while running because `CleanPause.Resume()` is a no-op unless Clean Pause owns the pause state.

### Enter Clean Pause

`clean_pause_start`:

1. verifies gameplay interception is active;
2. enables `clean_pause_only`;
3. verifies the pass filter is enabled;
4. calls `Game.PauseGame(true)`;
5. records `clean_paused` state.

No menu UI is opened.

### Resume

`clean_pause_resume`:

1. disables `clean_pause_only`;
2. calls `Game.PauseGame(false)`;
3. returns to `running`;
4. refreshes gameplay interception.

### Open vanilla pause menu

Start while clean-paused:

1. disables `clean_pause_only`;
2. disables `clean_pause_block_vanilla_pause` immediately;
3. releases Clean Pause's `Game.PauseGame(true)` ownership;
4. calls the real `MenuEvents.DisplayIngameMenu(true)` through `UIAction.CallFunction`;
5. lets KCD2's vanilla menu install/use its own `only_ui` lifecycle.

No UI event callback is required. While the vanilla menu is open, `only_ui` keeps our gameplay interception disabled. After the menu closes, the monitor sees `only_ui == false` and restores Clean Pause interception automatically.

If the menu bridge call fails, the transition rolls back to Clean Pause: native pause and both clean-pause filters are restored.

## Explicit emergency recovery

Development builds expose:

```text
clean_pause_disable
```

It releases a Clean Pause if owned, disables both custom filters, disables the custom action map, and restores vanilla pause behavior for the remainder of the session.

## Safety advantages

This design does not:

- call `InitActionMaps`;
- replace `defaultProfile.xml`;
- replace controller layouts;
- persist user keybind changes;
- replace `Menu.gfx`;
- depend on a free Xbox button;
- depend on `Player.OnAction` listener ordering;
- intentionally change main-menu input.

## Retail acceptance still required

Static/source research cannot prove presentation behavior in the shipped Xbox Store build. Before merge/release, test:

1. controller navigation is normal in the initial menu;
2. detected profile version is accepted and initialization succeeds;
3. first gameplay Start enters Clean Pause with **zero pause-menu frame/flash**;
4. the current frame remains visible;
5. the current subtitle remains visible indefinitely;
6. dialogue/cutscene progression and audio actually stop under `Game.PauseGame(true)`;
7. B resumes reliably while natively paused;
8. second Start opens the untouched vanilla pause menu;
9. B/Start/navigation inside the vanilla menu remain normal;
10. after closing the menu, Start again enters Clean Pause;
11. dialogue and in-engine cutscene action filters still allow the custom Start/B actions.

The last item is the remaining controller-context risk: other KCD2 `actionPass` filters can intersect with our custom action IDs. Existing cutscene-capable controller mods are strong precedent, but the retail test is authoritative.
