# Official-profile implementation plan

Primary target: KCD2 1.5.6, PC Xbox Store / Xbox app / Game Pass.

## Decision

Use the official KCD2 `.pak`/Lua path first. Native DLL/ASI remains fallback-only.

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

Each retail pause route is split into custom press + original release fallback:

```text
press
  -> clean_pause_enter_gameplay / clean_pause_enter_pause_context
  -> consoleCMD="1"
  -> CleanPause.Enter()

release
  -> original open_menu / open_pause_menu
  -> vanilla fallback
```

If Clean Pause succeeds, it enables `clean_pause_controls` before release and the explicit `clean_pause_block_start_release` sink consumes that release.

If the custom command/bootstrap fails, the controls map never activates and the original release opens normal vanilla pause.

### 5. Context/filter preservation — implemented

The custom entry action is mirrored anywhere an existing pause action appears in an `actionFail` filter. This includes the exact retail `no_menu` filter.

Relevant `actionPass` filters receive the custom entry plus all temporary Clean Pause controls.

The exact target profile contains no `actionPass` filters.

### 6. Clean Pause state machine — implemented for retail testing

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

The `MenuEvents` handoff remains a runtime gate.

### 7. Self-contained release source — complete

Versioned target source:

```text
vendor/kcd2/xbox-1.5.6/defaultProfile.clean-pause.xml.gz.b64
```

Current patched-profile SHA-256:

```text
9838db3747f7f36e0c9c281b8770bc7300998515407515b65493b8e9a9bcd14e
```

`tools/build_release.py` verifies the hash and the full fail-safe XML contract before packaging.

### 8. Static validation — implemented

CI proves:

- Lua 5.1 syntax;
- exact `consoleCMD` spelling and absence of wrong-case `consoleCmd`;
- original pause actions remain release-only, non-console fallbacks;
- custom entries are press-only Escape/Start console commands;
- exclusive controls map contains Start/Escape release and B press sinks;
- actionFail/actionPass mirroring;
- forbidden runtime input mutation remains absent;
- synthetic development build succeeds;
- self-contained retail release build contains the same contract.

### 9. GitHub release flow — implemented

Normal flow:

```text
implementation PR -> merge
release PR changes VERSION -> CI -> merge
main Release workflow -> tag v<VERSION> -> ZIP + SHA256SUMS -> GitHub Release
```

No generated ZIP/PAK is committed. No Actions Secret or user game file is required at publication time.

### 10. Xbox Store 1.5.6 rc2 retail acceptance — next

Must prove in order:

1. Escape and Xbox Start are never dead controls;
2. corrected custom press route enters Clean Pause;
3. successful entry consumes the corresponding release;
4. if custom entry cannot execute, vanilla release fallback still opens pause;
5. first Clean Pause has zero vanilla-menu frame;
6. subtitle/frame remain visible;
7. unrelated input is isolated;
8. B resumes without dialogue/cutscene skip;
9. second Escape/Start opens the real vanilla menu;
10. dialogue/cutscene/audio progression resumes coherently.

See `docs/TESTING.md`.

## Compatibility policy

`defaultProfile.xml` is a whole-file conflict point. The release source is pinned to KCD2 1.5.6 and conflicts with another mod that replaces that file unless intentionally merged.

A new KCD2 version requires regeneration/review of the target profile and a new release.

## Native fallback criteria

Return to native input interception only if retail testing proves an essential behavior cannot be delivered safely through the official profile/Lua path. A failure of one uncertain API is not enough by itself; the official route must first exhaust safe fallbacks.
