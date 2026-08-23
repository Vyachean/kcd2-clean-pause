# Official-profile implementation plan

Primary target: KCD2 1.5.6, PC Xbox Store / Xbox app / Game Pass.

## Decision

Use the official KCD2 `.pak`/Lua path first. Native DLL/ASI code remains fallback-only and is not part of the current test candidate.

## Stage status

### 1. Establish exact retail Start routes — complete

Confirmed effective profile routes:

```text
open_menu/open_menu             -> xi_start
open_pause_menu/open_pause_menu -> xi_start
```

### 2. Exact-profile builder — complete

`tools/build_from_game.py` reads the target installation's own `Data/IPL_GameData.pak`, fails closed unless the expected 1.5.6 structure exists, and patches both retail Start actions while preserving action IDs and physical bindings.

### 3. Clean Pause state machine — complete for retail testing

```text
Running + routed Start
  -> enable clean_pause_controls
  -> Game.PauseGame(true)
  -> CleanPaused

CleanPaused + B release
  -> disable clean_pause_controls
  -> Game.PauseGame(false)
  -> Running

CleanPaused + Start
  -> disable clean_pause_controls
  -> MenuEvents.DisplayIngameMenu(true)
  -> vanilla menu owns pause lifecycle
```

### 4. Input isolation without retail `EnableActionFilter` — complete for retail testing

The old design incorrectly depended on `ActionMapManager.EnableActionFilter`, which is not in the target retail Lua method list.

Replacement:

```xml
<actionmap name="clean_pause_controls"
           priority="overlays"
           exclusivity="1">
```

The map has a Start handoff action, a B-press sink and a B-release resume action. Relevant existing `actionPass` filters are extended; existing `actionFail` restrictions are preserved.

### 5. Static validation/documentation — complete

CI covers Lua syntax, exact-profile patch unit tests, both routed Start actions, overlay-priority/exclusive controls, B press/release contract, actionPass extension, forbidden runtime mutation checks, and a synthetic exact-profile build.

The synthetic artifact is never published as an installable mod.

### 6. Xbox Store 1.5.6 retail acceptance — next

Must prove:

1. title/front-end controller remains normal;
2. first Start enters Clean Pause with zero menu frame;
3. current subtitle remains visible;
4. overlay-priority exclusivity isolates unrelated input;
5. B resumes without dialogue/cutscene skip;
6. second Start opens the real vanilla pause menu through `MenuEvents`;
7. closing that menu returns to ordinary gameplay;
8. dialogue/cutscene/audio progression pauses and resumes coherently.

See `docs/TESTING.md`.

## Compatibility policy

`defaultProfile.xml` is a whole-file conflict point. Never ship a stale copied retail profile; always build from the installation being tested; test without another mod replacing `defaultProfile.xml`; document manual merging if this becomes the release implementation.

## Native fallback criteria

Revisit native code only if retail testing proves that a required behaviour cannot be achieved through this official path, especially input isolation, menu handoff, zero-overlay entry, or subtitle/frame retention.
