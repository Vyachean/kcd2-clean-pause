# Testing

Primary acceptance target: **Windows Xbox Store / Xbox app, KCD2 1.5.6, Xbox controller**.

## Confirmed result from the first PR #2 build

The first action-filter build was tested on Xbox Store PC 1.5.6:

- controller input remained functional;
- Menu / Start behaved exactly like vanilla KCD2;
- no Clean Pause occurred.

That build therefore failed product acceptance, but its fail-safe succeeded.

## Current diagnostic build: safe Start handshake

The current revision deliberately does **not** block KCD2's `ui_start_pause` at startup.

It first requires proof that the supplemental controller action really works on the retail build:

```text
first gameplay Start press
  |
  +-- vanilla ui_start_pause  -> allowed normally
  |
  +-- clean_pause_start       -> if this fires, remember handshake
```

So the **first Start press after loading a save is expected to open the ordinary KCD2 pause menu**.

After that menu is closed, and only if `clean_pause_start` was observed, the narrow action filter becomes eligible:

```text
second gameplay Start press
  |
  +-- vanilla ui_start_pause -> blocked before UI dispatch
  |
  +-- clean_pause_start      -> Game.PauseGame(true)
```

This development handshake prevents an unproven custom action map from ever taking the normal pause button away from the user.

## Test A — controller safety

1. Start KCD2 with the controller connected.
2. Confirm the initial/front-end menu works normally.
3. Load a save.
4. Confirm movement, camera, face buttons, shoulders/triggers, D-pad, sticks, View and Menu/Start are otherwise normal.

Any global controller failure is an immediate regression.

## Test B — input handshake

Use ordinary exploration, not dialogue/cutscene yet.

1. Press Menu / Start once.
2. **Expected:** the ordinary vanilla pause menu opens. This is intentional for this diagnostic revision.
3. Close the vanilla pause menu normally.
4. Wait about 1–2 seconds.
5. Press Menu / Start again.

### Outcome B1 — second Start enters Clean Pause

This proves on Xbox Store 1.5.6 that all of these work:

- effective profile version gate;
- `ActionMapManager.LoadFromXML` for the supplemental profile;
- custom `clean_pause_controls` map;
- physical `xi_start` binding;
- console-command dispatch to `clean_pause_start`;
- narrow `ui_start_pause` filter.

Proceed to the pause behavior tests below.

Expected log sequence contains:

```text
[Clean Pause] controller Start handshake observed; first pause intentionally left vanilla
[Clean Pause] vanilla pause interception=true
[Clean Pause] entered native clean pause
```

### Outcome B2 — second Start is also ordinary vanilla pause

Stop functional testing. The input interception layer is still not armed.

At that point the useful evidence is the `[Clean Pause]` section from `kcd.log`. Relevant distinctions are:

```text
unsupported defaultProfile.xml version ...
cannot read Libs/Config/defaultProfile.xml ...
supplemental filters not loaded ...
initialized safely ... waiting for first gameplay Start handshake
controller Start handshake observed ...
```

If initialization succeeded but the handshake line never appears, the supplemental `xi_start` action itself is not reaching the console-command action on this build/context.

Do **not** respond by blindly enabling the vanilla-pause filter; that would risk making Start stop working.

## Test C — Clean Pause visual behavior

Only after B1 succeeds:

1. From active gameplay press Menu / Start.
2. World simulation should stop immediately.
3. The vanilla pause menu must not appear, even for a single rendered frame.
4. No darkening/fade/replacement screen should appear.
5. Current HUD/frame should remain visible.

Expected log:

```text
[Clean Pause] entered native clean pause
```

## Test D — resume

While clean-paused:

1. press B once;
2. world simulation should resume immediately;
3. normal gameplay input should return.

Expected log:

```text
[Clean Pause] resumed from native clean pause
```

## Test E — vanilla-menu handoff

1. Enter Clean Pause.
2. Press Menu / Start while clean-paused.
3. The real KCD2 pause menu should open.
4. Navigate and close it normally.
5. After returning to gameplay, wait about 1–2 seconds.
6. Menu / Start should again enter Clean Pause.

Expected handoff log:

```text
[Clean Pause] handed pause ownership to vanilla menu
```

## Test F — subtitle requirement

This is the core product requirement.

1. Start a normal dialogue with subtitles enabled.
2. Wait for a subtitle line to be clearly visible.
3. Press Menu / Start.
4. Leave the game paused longer than that line would normally remain visible.
5. Confirm the **same subtitle remains visible**.
6. Press B to resume.
7. Confirm dialogue continues without skipped/duplicated lines or desynchronization.

Repeat in an in-engine cutscene.

If Clean Pause works in exploration but Start becomes vanilla/unresponsive in dialogue or a cutscene, treat that as a context-specific action-filter problem; do not change the pause primitive yet.

## Test G — native pause/audio

The prototype uses:

```lua
Game.PauseGame(true)
```

Verify independently:

- speech audio stops;
- animation/camera progression stops;
- dialogue timing stops;
- scripted events do not advance;
- current subtitle stays visible;
- resume continues coherently.

If frame/subtitles remain but audio continues, input routing is solved and the remaining problem is a Warhorse audio/dialogue subsystem.

## Lifecycle regression tests

After the basic flow works, verify:

- initial/front-end menu remains vanilla;
- inventory/map/journal remain normal;
- repeated pause/resume cycles;
- Clean Pause -> vanilla menu -> gameplay;
- Clean Pause -> vanilla menu -> load save;
- return to main menu;
- controller disconnect/reconnect;
- Alt-Tab while paused.

No transition may leave native pause or custom input filtering active after Clean Pause no longer owns the state.

## Logging

Search `kcd.log` for:

```text
[Clean Pause]
```

The development command below also writes the current state to the log if a console is available:

```text
clean_pause_status
```

Emergency session recovery:

```text
clean_pause_disable
```

Removing the mod and restarting must always restore fully vanilla input without editing user settings.

## Release gate

A release candidate requires:

- no controller regression in front-end or gameplay;
- no persistent keybind/profile modification;
- direct gameplay Start -> Clean Pause without the development first-press handshake;
- zero visible pause-menu overlay;
- normal gameplay, dialogue and in-engine cutscene support;
- current subtitle remains visible indefinitely;
- native pause stops audio/cutscene progression coherently;
- B resumes reliably;
- Start from Clean Pause opens untouched vanilla menu;
- vanilla menu remains fully usable;
- uninstall requires no controller/config repair.

The one-time vanilla first press is acceptable only in diagnostic builds and must be removed after the retail input path is proven.