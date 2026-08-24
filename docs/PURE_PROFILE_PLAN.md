# Official-profile implementation plan

> **Status: superseded historical plan.** This document records the rc.1/rc.2 pure-profile direction and must not be used as the current implementation plan. Retail testing later rejected this architecture. See [STATUS_AND_PLAN.md](STATUS_AND_PLAN.md) and [DESIGN.md](DESIGN.md) for the active hidden-vanilla-pause design.

Primary target: KCD2 1.5.6, PC Xbox Store / Xbox app / Game Pass.

## Historical decision

At this stage of the project the plan was to use the official KCD2 `.pak`/Lua path first and keep native code as fallback-only. Subsequent retail evidence superseded that decision.

## Stage status

### 1. Establish exact retail pause routes — complete

Confirmed in the extracted Xbox Store 1.5.6 profile:

```text
open_menu/open_menu             -> keyboard=_keybinds_ref_, xboxpad=xi_start
open_pause_menu/open_pause_menu -> keyboard=_keybinds_ref_, xboxpad=xi_start
overlays priority               -> 12
```

### 2. Exact-profile development builders — complete

- `tools/build_from_game.py` reads `Data/IPL_GameData.pak`;
- `tools/build_from_profile.py` accepts an extracted `defaultProfile.xml`.

Both fail closed when the expected target structure is absent.

### 3. rc1 retail test — failed, root cause confirmed

`v0.1.0-rc.1` produced no pause from either Escape or Xbox Start.

Root cause:

- rc1 emitted `consoleCmd="1"`;
- KCD2 keybind actions use exact `consoleCMD="1"`;
- rc1 had replaced the original pause route completely, so command failure also removed vanilla pause.

rc1 is not a valid acceptance candidate.

### 4. Fail-safe pause entry — implemented for rc2

Each retail pause route was split into custom press + original release fallback:

```text
press
  -> clean_pause_enter_gameplay / clean_pause_enter_pause_context
  -> consoleCMD="1"
  -> CleanPause.Enter()

release
  -> original open_menu / open_pause_menu
  -> vanilla fallback
```

If Clean Pause succeeded, it enabled `clean_pause_controls` before release and the explicit `clean_pause_block_start_release` sink consumed that release.

If the custom command/bootstrap failed, the intended fallback was for the original release to open normal vanilla pause.

Retail rc.2 testing showed this fallback assumption was not sufficient: Escape/Start could still become dead. That failure is one of the reasons this architecture is superseded.

### 5. Context/filter preservation — historical implementation

The custom entry action was mirrored anywhere an existing pause action appeared in an `actionFail` filter, including the exact retail `no_menu` filter.

Relevant `actionPass` filters received the custom entry plus all temporary Clean Pause controls.

The exact target profile contained no `actionPass` filters.

### 6. Historical Clean Pause state machine

```text
Running + custom press
  -> enable clean_pause_controls
  -> Game.PauseGame(true)
  -> CleanPaused

CleanPaused + B release
  -> disable clean_pause_controls
  -> Game.PauseGame(false)
  -> Running

CleanPaused + Escape/Start press
  -> disable clean_pause_controls
  -> MenuEvents.DisplayIngameMenu(true)
  -> vanilla menu owns pause lifecycle
```

This state machine is rejected. Later retail testing established that the relevant custom pause primitives either were unavailable or did not reproduce the full vanilla pause lifecycle.

### 7. Self-contained release source — historical

The pure-profile release path versioned a reviewed target profile under `vendor/kcd2/xbox-1.5.6/` and generated the `.pak`/ZIP in CI.

The active native release no longer depends on a full `defaultProfile.xml` replacement.

### 8. Static validation — historical

CI for this path proved profile/Lua structure and packaging, but static validation could not prove the critical retail behavior. The rc.1/rc.2 failures demonstrated that distinction.

### 9. GitHub release flow — retained conceptually

The normal release flow remains:

```text
implementation PR -> merge
release PR changes VERSION -> CI -> merge
main Release workflow -> tag v<VERSION> -> ZIP + SHA256SUMS -> GitHub Release
```

Generated release artifacts are not committed.

### 10. Retail acceptance — failed for this architecture

The expected rc.2 acceptance gates were not met. In particular, the design could not guarantee that Escape/Start remained valid vanilla pause controls under custom profile routing.

## Historical compatibility issue

`defaultProfile.xml` is a whole-file last-mod-wins conflict point. Any production design based on replacing it would conflict with another mod that replaces the same file unless deliberately merged.

Avoiding that conflict is an additional benefit of the current native presentation-only architecture.

## Current decision

Do **not** return to this pure-profile plan merely because a newer native experiment fails.

The active rule is:

> keep vanilla KCD2 pause ownership intact and modify only the visible pause-menu presentation after pause state is verified.

See [STATUS_AND_PLAN.md](STATUS_AND_PLAN.md).
