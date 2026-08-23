# Testing

A build is not releasable until the clean-pause behaviour is tested in the retail game. The Xbox Store / Xbox app PC build is the primary acceptance target.

## Safety gate

Run this before testing any pause behaviour:

- start KCD2 with an Xbox controller connected;
- verify controller navigation works in the initial menu;
- load a save;
- verify movement, camera, face buttons, triggers, shoulders, sticks, D-pad, View and Menu behave normally;
- return to the initial menu and verify controller navigation again.

**Any build that disables or globally changes unrelated controller input fails immediately.**

## Core acceptance matrix

| Scenario | Enter clean pause | Frame remains visible | Subtitle remains visible | Resume works | Vanilla menu reachable |
| --- | --- | --- | --- | --- | --- |
| Normal exploration | required | required | n/a | required | required |
| Combat | required | required | if present | required | required |
| Normal dialogue | required | required | **required** | required | required |
| In-engine cutscene | required | required | **required** | required | required |
| Mounted gameplay | required | required | if present | required | required |
| Inventory/map closed, return to world | required | required | n/a | required | required |

Prerendered video should be tested separately; support may be engine-limited.

## Preferred input acceptance

Target behaviour:

1. From `Running`, press Xbox **Menu / Start** once.
2. The vanilla pause menu must **not** appear.
3. The game enters `CleanPaused` with the current frame unobscured.
4. Trigger the resume action: the game returns to exactly the previous running state.
5. Enter `CleanPaused` again.
6. Press **Menu / Start** again.
7. Clean Pause releases its own freeze state and KCD2's normal pause menu opens.
8. Closing the vanilla menu must leave controls and game state consistent.

The resume button is not fixed until the pause-action interception strategy is proven.

## State restoration

Test with non-default time scale if possible:

1. Set a known non-1.0 `t_scale`.
2. Enter Clean Pause.
3. Resume.
4. Confirm the exact previous value is restored.

Also test that Clean Pause refuses to steal ownership if the game is already frozen by another mechanism.

## Transition robustness

Attempt these only after the basic flow works:

- pause near a dialogue transition;
- pause near a cutscene transition;
- pause, open vanilla pause menu, then load a save;
- pause before death/game-over transition;
- pause while mounted;
- pause while hard-locked in combat;
- disconnect/reconnect the controller while clean-paused;
- Alt-Tab while clean-paused;
- return to main menu after using Clean Pause several times.

No transition may leave `t_scale == 0` after Clean Pause no longer owns the state.

## Logging

Development builds should log state transitions with a stable prefix:

```text
[Clean Pause]
```

Useful events:

- mod loaded;
- input hook installed / failed;
- vanilla pause action observed;
- vanilla pause action consumed;
- enter CleanPaused with captured previous state;
- resume with restored state;
- handoff to vanilla menu;
- forced cleanup/recovery.

Do not spam per-frame logs in normal builds.

## Release gate

A release candidate requires:

- no controller regression in the initial menu;
- no replacement of unrelated keybindings;
- clean pause works in normal gameplay;
- clean pause works in normal dialogue;
- subtitle persistence is verified;
- clean pause works in at least one in-engine cutscene;
- resume cannot strand the game at zero time scale;
- vanilla pause menu remains accessible;
- uninstalling the mod restores completely vanilla behaviour without repairing user config files.
