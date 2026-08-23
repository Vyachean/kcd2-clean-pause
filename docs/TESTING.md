# Testing

A build is not releasable until Clean Pause is tested in the retail game. The Windows Xbox Store / Xbox app build with an Xbox controller is the primary acceptance target.

## Prototype under test

The `prototype/action-filter` branch uses a supplemental action map plus narrowly scoped action filters.

It does **not** replace the game's profile/controller layout and does not call `InitActionMaps`.

Expected gameplay routing:

```text
Menu / Start
  physical xi_start
      |
      +-- vanilla ui_start_pause -> blocked before UI dispatch
      |
      +-- clean_pause_start      -> Game.PauseGame(true)
                                    -> no menu UI
```

While clean-paused:

```text
B            -> clean_pause_resume -> Game.PauseGame(false)
Menu / Start -> clean_pause_start  -> real MenuEvents.DisplayIngameMenu(true)
```

Outside active gameplay, or while KCD2's `only_ui` filter is active, the mod drops its `ui_start_pause` block so ordinary UI/menu behavior remains vanilla.

## Safety gate

Do this before evaluating subtitle behavior.

### Initial/front-end menu

1. Start KCD2 with the controller connected.
2. Navigate the initial menu with sticks/D-pad/A/B.
3. Press Menu / Start where it normally has meaning.
4. Confirm no controller input has globally disappeared.

Expected log if initialization succeeds:

```text
[Clean Pause] initialized safely; profile version=...
```

If the retail `defaultProfile.xml` version is unsupported, expected behavior is instead:

```text
[Clean Pause] unsupported defaultProfile.xml version ...; vanilla controls unchanged
```

That is a safe compatibility failure, not a controller failure.

**Stop immediately** if ordinary controller input disappears. Remove the mod and preserve `kcd.log`.

### Loaded gameplay

After loading a save, verify before pressing Start:

- movement;
- camera;
- A/B/X/Y;
- LB/RB/LT/RT;
- both stick clicks;
- D-pad;
- View;
- Menu / Start has not caused any unrelated mapping regression.

## First Clean Pause test

Use ordinary exploration.

1. Press Menu / Start once.
2. The world should stop immediately.
3. The vanilla pause menu must **not appear at all**.
4. There must be no darkening/fade/replacement screen.
5. The current HUD/frame should remain exactly where it was.

Expected log:

```text
[Clean Pause] entered native clean pause
```

A single visible pause-menu frame is a failure of the product requirement.

Unlike the discarded `Player.OnAction` prototype, the action-filter design should not rely on same-frame cancellation: `ui_start_pause` should be removed before the UI listener receives it.

## Resume test

While clean-paused:

1. press B once;
2. world simulation should resume immediately;
3. normal gameplay input should be restored.

Expected log:

```text
[Clean Pause] resumed from native clean pause
```

If B does not work, do not repeatedly mash controller buttons. Try Menu / Start once to test the vanilla-menu recovery path, then exit and preserve the log.

## Vanilla-menu handoff

1. Enter Clean Pause again.
2. Press Menu / Start again.
3. The real KCD2 pause menu should open.
4. Navigate it normally.
5. Verify both B and the normal Menu/Start behavior inside the menu.
6. Close the menu.
7. Wait a fraction of a second for lifecycle refresh.
8. Press Menu / Start again from gameplay; it should enter Clean Pause again.

Expected handoff log:

```text
[Clean Pause] handed pause ownership to vanilla menu
```

The prototype removes its vanilla-pause block before invoking `MenuEvents.DisplayIngameMenu(true)`. KCD2's own `only_ui` filter then owns menu input. After the menu closes, the lifecycle monitor restores gameplay interception.

## Main-menu return / lifecycle test

This specifically guards against the earlier global-action-map failure class.

1. Use Clean Pause several times.
2. Open the vanilla pause menu.
3. Return to the game's main/front-end menu.
4. Confirm controller navigation remains completely normal.
5. Load a save again.
6. Confirm Clean Pause becomes available again without restarting the game if the mod scripts remain loaded.

No `ui_start_pause` interception is allowed while `player == nil`.

## Core acceptance matrix

| Scenario | Enter clean pause | Zero visible overlay | Frame remains visible | Subtitle remains visible | Resume works | Vanilla menu reachable |
| --- | --- | --- | --- | --- | --- | --- |
| Normal exploration | required | required | required | n/a | required | required |
| Combat | required | required | required | if present | required | required |
| Normal dialogue | required | required | required | **required** | required | required |
| In-engine cutscene | required | required | required | **required** | required | required |
| Mounted gameplay | required | required | required | if present | required | required |

Prerendered video is a separate capability test and may be engine-limited.

## Subtitle test

This is the critical product test.

1. Start a normal dialogue with subtitles enabled.
2. Wait until a subtitle line is clearly visible.
3. Press Menu / Start.
4. Leave the game paused longer than that line would normally remain visible.
5. Confirm the **same subtitle remains visible**.
6. Press B.
7. Confirm dialogue continues without a skipped/duplicated line or desynchronization.

Repeat in an in-engine cutscene.

If Start works in exploration but not in dialogue/cutscene, capture the log. That likely means a KCD2 context-specific `actionPass` filter is excluding the custom action IDs; it is an input-filter compatibility problem, not a native-pause problem.

## Native pause/audio test

The prototype uses:

```lua
Game.PauseGame(true)
```

instead of `t_scale 0`.

Verify independently:

- speech audio stops;
- animation/camera progression stops;
- dialogue timing stops;
- scripted events do not advance;
- current subtitle stays visible;
- resume continues coherently.

If the frame/subtitle remain but audio continues, record that separately. It would indicate a Warhorse audio subsystem outside native pause rather than an input-routing failure.

## UI-context regression test

Open ordinary game UIs where practical:

- inventory;
- map;
- journal/quest UI;
- vanilla pause menu.

Verify that B, Start and navigation retain normal behavior. The lifecycle logic specifically drops `ui_start_pause` interception whenever the game's existing `only_ui` filter is active.

If some UI does not use `only_ui` and Start behaves like Clean Pause there, record which UI. The interceptor may need a broader menu-context predicate before release.

## Transition robustness

After the basic flow works, test:

- repeated pause/resume cycles;
- pause near a subtitle transition;
- pause near a cutscene transition;
- Clean Pause -> vanilla menu -> load a save;
- death/game-over transition;
- mounted gameplay;
- hard-lock combat;
- controller disconnect/reconnect while clean-paused;
- Alt-Tab while clean-paused;
- return to main menu after several cycles.

No transition may leave the game natively paused after Clean Pause no longer owns the pause state.

## Logging

Search `kcd.log` for:

```text
[Clean Pause]
```

Useful success lines:

```text
initialized safely; profile version=...
entered native clean pause
resumed from native clean pause
handed pause ownership to vanilla menu
player disappeared; clean pause recovered
disabled; vanilla pause action restored
```

Compatibility/safety failures include:

```text
cannot read Libs/Config/defaultProfile.xml; input hook not installed
cannot determine defaultProfile.xml version; input hook not installed
unsupported defaultProfile.xml version ...; vanilla controls unchanged
custom input profile missing; vanilla controls unchanged
supplemental filters not loaded; vanilla controls unchanged
lifecycle monitor could not be scheduled; disabling interception
```

## Emergency session recovery

If the console is available, development builds expose:

```text
clean_pause_disable
```

It disables the supplemental action map/filters and restores vanilla pause routing for the current session.

A restart after removing the mod must always return to completely vanilla input without editing user configuration.

## Release gate

A release candidate requires all of the following:

- no controller regression in initial/front-end menu;
- no persistent keybind/profile modification;
- first gameplay Menu/Start produces **zero visible pause-menu overlay**;
- normal gameplay pause works;
- dialogue pause works;
- in-engine cutscene pause works;
- current subtitle remains visible indefinitely while paused;
- native pause stops audio/cutscene progression coherently;
- B resumes reliably;
- second Start opens the untouched vanilla pause menu;
- vanilla menu controls/closing remain normal;
- returning to front-end menu leaves controls vanilla;
- uninstall requires no controller/config repair.
