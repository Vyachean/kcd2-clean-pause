# Testing

A build is not releasable until the clean-pause behaviour is tested in the retail game. The Xbox Store / Xbox app PC build is the primary acceptance target.

## Current prototype under test

The current source does **not** install controller mappings.

It wraps KCD2's existing `Player.OnAction` and watches:

```text
ui_start_pause
ui_back
```

The intended first-press flow is:

```text
Menu / Start
  -> vanilla ui_start_pause path
  -> close vanilla ingame menu via MenuEvents.DisplayIngameMenu(false)
  -> Game.PauseGame(true)
  -> enable existing only_ui filter
  -> CleanPaused with no visible menu
```

While clean-paused:

```text
B / ui_back  -> Resume
Menu / Start -> Vanilla pause menu
```

This test is specifically intended to determine whether the vanilla menu can be cancelled before it is rendered.

## Safety gate

Run this **before** evaluating pause behaviour:

1. Start KCD2 with an Xbox controller connected.
2. Verify controller navigation works in the initial menu.
3. Load a save.
4. Verify movement, camera, face buttons, triggers, shoulders, sticks, D-pad, View and Menu operate normally.
5. Return to the initial menu and verify navigation again if practical.

**Any build that disables or globally changes unrelated controller input fails immediately.**

The current prototype contains no `InitActionMaps`, custom action map, controller-layout replacement or persistent remapping. A main-menu controller regression would therefore be unexpected and must be treated as a stop condition.

## First diagnostic test

Do this in ordinary exploration before a dialogue/cutscene.

### 1. First Menu / Start press

Press Menu / Start once.

Record exactly one of these outcomes:

#### A — ideal

- world freezes;
- **no vanilla pause-menu frame is visible at all**;
- current HUD/frame remains visible.

This validates the same-cycle cancellation approach.

#### B — menu flashes briefly, then disappears

The bridge works, but ordering requires a deferred finalizer and the current implementation does not yet meet the zero-overlay requirement.

#### C — vanilla menu remains open

Check `kcd.log` for `[Clean Pause]` lines. Important distinctions:

- no `observed ui_start_pause` -> Player hook is not seeing the action in this retail route;
- action observed + `MenuEvents... unavailable` -> event-system name/API differs on KCD2;
- action observed + `entered native clean pause` but menu remains -> Player hook ran before the vanilla UI handler, so the menu opened after our synchronous cancellation.

Do not treat C as a release failure only; it tells us which next hook is needed.

### 2. Resume with B

If clean pause was reached, press B once.

Expected:

- `[Clean Pause] observed ui_back while clean-paused` in the log;
- world resumes immediately;
- normal controls return.

If B does nothing but Start still works, do not force-close the game immediately: press Start and check whether the normal pause menu is reachable. Then exit and send the log.

### 3. Vanilla-menu handoff

Enter clean pause again, then press Menu / Start.

Expected:

- KCD2's normal pause menu appears;
- Clean Pause logs `handed pause ownership to vanilla menu`;
- closing the normal menu returns to ordinary gameplay;
- Clean Pause does not silently reactivate.

## Core acceptance matrix

Only after the diagnostic flow works:

| Scenario | Enter clean pause | Zero visible overlay | Frame remains visible | Subtitle remains visible | Resume works | Vanilla menu reachable |
| --- | --- | --- | --- | --- | --- | --- |
| Normal exploration | required | required | required | n/a | required | required |
| Combat | required | required | required | if present | required | required |
| Normal dialogue | required | required | required | **required** | required | required |
| In-engine cutscene | required | required | required | **required** | required | required |
| Mounted gameplay | required | required | required | if present | required | required |

Prerendered video is a separate capability test and may be engine-limited.

## Subtitle test

The critical product test:

1. Start a normal dialogue with subtitles enabled.
2. Wait until a subtitle line is clearly visible.
3. Press Menu / Start.
4. Leave the game paused longer than the subtitle would normally remain on screen.
5. Confirm the **same subtitle remains visible**.
6. Press B to resume.
7. Confirm dialogue continues normally without skipped/duplicated lines or audio desync.

Repeat in an in-engine cutscene.

## Audio/cutscene test

Because the prototype now uses native `Game.PauseGame(true)` rather than `t_scale 0`, verify:

- speech audio stops rather than continuing underneath the frozen image;
- animation/camera progression stops;
- scripted events do not advance;
- resume continues coherently.

If native pause preserves the subtitle but audio continues, record that separately; it may identify a Warhorse-specific subsystem that needs a narrow additional pause mechanism.

## Visual-flash test

A menu that appears for even one rendered frame violates the final goal.

For the first prototype, inspect carefully for:

- darkening/fade;
- menu background;
- cursor/focus change;
- HUD disappearing then returning;
- subtitle disappearing/reappearing.

If uncertain, record a 60 fps or higher screen capture and inspect frame-by-frame.

A single visible flash means the synchronous Player hook is too late/early for the final implementation even if the game ends up clean-paused.

## Transition robustness

After basic behaviour works, test:

- repeated pause/resume cycles;
- pause near a dialogue line transition;
- pause near a cutscene transition;
- clean pause -> vanilla menu -> load a save;
- death/game-over transition;
- mounted gameplay;
- hard-lock combat;
- controller disconnect/reconnect while clean-paused;
- Alt-Tab while clean-paused;
- return to main menu after several cycles.

No transition may leave the game paused after Clean Pause no longer owns the pause state.

## Logging

Search `kcd.log` for:

```text
[Clean Pause]
```

Expected useful lines include:

```text
Player.OnAction hook installed
prototype loaded; no controller mappings modified
observed ui_start_pause; state=running
entered native clean pause
observed ui_back while clean-paused
resumed from native clean pause
handed pause ownership to vanilla menu
```

Failure diagnostics include:

```text
MenuEvents bridge unavailable
MenuEvents.DisplayIngameMenu(...) unavailable
clean-pause entry aborted; vanilla pause remains authoritative
clean-pause entry rolled back to vanilla menu
```

Do not enable per-frame logging.

## Release gate

A release candidate requires:

- no controller regression in initial/front-end menu;
- no replacement of unrelated keybindings;
- first Menu/Start produces **zero visible pause-menu overlay**;
- clean pause works in ordinary gameplay;
- clean pause works in normal dialogue;
- current subtitle remains visible indefinitely while paused;
- clean pause works in at least one in-engine cutscene;
- audio/cutscene progression pauses coherently;
- B resumes reliably;
- second Menu/Start opens the untouched vanilla pause menu;
- vanilla menu closes normally;
- uninstalling the mod returns completely vanilla behaviour without repairing controller configuration.
