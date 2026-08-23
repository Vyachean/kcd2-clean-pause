# Deterministic action-filter prototype

This document describes the preferred next prototype. It supersedes the timing-dependent `Player.OnAction` cancellation experiment if retail loading succeeds.

## Why this approach

CryEngine evaluates action filters before an action is added to the event priority list. Therefore an `actionFail` filter containing only `ui_start_pause` prevents KCD2's vanilla pause action from ever reaching its UI blocking listener, while a separate custom action bound to the same physical Xbox Menu/Start input can still run because it has a different action ID.

Conceptually:

```text
physical xi_start
  |
  +-- ui_start_pause       -- filtered before dispatch
  |
  +-- clean_pause_start    -- allowed -> CleanPause.StartPressed()
```

This removes the ordering/race problem of trying to close the vanilla pause menu after it starts.

## Required XML pieces

The runtime-loaded XML should define:

1. a uniquely named action map with:
   - `clean_pause_start` on `xi_start`;
   - `clean_pause_resume` on `xi_b`;
2. an `actionFail` filter containing only `ui_start_pause`;
3. an `actionPass` filter containing only the two Clean Pause actions for clean-paused input isolation.

Illustrative structure:

```xml
<profile version="22">
  <actionmap name="clean_pause_controls" version="22">
    <action
      name="clean_pause_start"
      consoleCmd="1"
      onPress="1"
      xboxpad="xi_start" />
    <action
      name="clean_pause_resume"
      consoleCmd="1"
      onPress="1"
      xboxpad="xi_b" />
  </actionmap>

  <actionfilter name="clean_pause_block_vanilla_pause" type="actionFail">
    <filter name="ui_start_pause" />
  </actionfilter>

  <actionfilter name="clean_pause_only" type="actionPass">
    <filter name="clean_pause_start" />
    <filter name="clean_pause_resume" />
  </actionfilter>
</profile>
```

The root/action-map version must be verified against current KCD2 before this is treated as production configuration. Existing KCD/CryEngine profiles and working KCD2 custom action examples use action-map version `22`, but the retail KCD2 root profile has not yet been directly extracted into this repository.

## Runtime states

### Installation/bootstrap

Before mutating action-map state:

1. prove `ActionMapManager.LoadFromXML` exists;
2. prove the vanilla menu bridge is available;
3. load the uniquely named map/filters with `LoadFromXML`;
4. enable only the custom map and `clean_pause_block_vanilla_pause` filter.

If any prerequisite fails, do not enable the filter. Vanilla pause must remain usable.

### Running

Enabled:

- `clean_pause_controls` action map;
- `clean_pause_block_vanilla_pause` actionFail filter.

Disabled:

- `clean_pause_only` actionPass filter.

Result:

- all ordinary KCD2 actions work except `ui_start_pause`;
- physical Menu/Start invokes `clean_pause_start` instead;
- custom B action may also dispatch but is a no-op while running.

### Enter Clean Pause

`clean_pause_start`:

1. call `Game.PauseGame(true)`;
2. enable `clean_pause_only`.

Because `clean_pause_only` is an `actionPass`, only `clean_pause_start` and `clean_pause_resume` continue through the action manager. Ordinary gameplay/UI actions are isolated without changing bindings.

### Resume

`clean_pause_resume`:

1. disable `clean_pause_only`;
2. call `Game.PauseGame(false)`;
3. return to Running.

### Open vanilla pause menu

`clean_pause_start` while clean-paused:

1. disable `clean_pause_only`;
2. temporarily disable `clean_pause_block_vanilla_pause` if full vanilla Start semantics are required inside the menu;
3. invoke `MenuEvents.DisplayIngameMenu(true)`;
4. let the vanilla menu own pause/input lifecycle.

The preferred production version should listen to `MenuEvents.OnStopIngameMenu` and restore `clean_pause_block_vanilla_pause` when the vanilla menu closes. If this event listener is unavailable on retail KCD2, the simpler fallback is to keep the pause-block filter enabled while the vanilla menu is open; B will still close the menu, but Start-to-close may be unavailable.

## Safety advantage

Unlike the discarded prototypes, this design does not:

- call `InitActionMaps`;
- replace existing action maps;
- edit persistent controller configuration;
- rely on a free controller button;
- rely on `Player.OnAction` ordering;
- allow the vanilla pause action and Clean Pause action to execute simultaneously.

`LoadFromXML` still needs retail validation because it changes the in-memory action manager. The load must happen only after all prerequisites are known and must use unique map/filter names.

## Evidence still required

Before merging this design as the default implementation:

- verify the XML root/action-map version on current retail KCD2;
- verify `LoadFromXML` accepts the custom map plus filters without disturbing existing maps;
- verify `xi_start` and `xi_b` custom actions dispatch on Xbox Store PC;
- verify `ui_start_pause` is actually suppressed when the filter is enabled;
- verify `clean_pause_only` still permits the custom actions while native game pause is active;
- verify `MenuEvents.OnStopIngameMenu` can be observed if used for filter restoration;
- verify current subtitle visibility under `Game.PauseGame(true)`.
