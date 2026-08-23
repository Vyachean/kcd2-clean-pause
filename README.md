# KCD2 Clean Pause

A small mod for **Kingdom Come: Deliverance II** whose goal is to provide a real pause that **does not cover or replace the current game image**.

## Goal

When the player pauses, the game should stop while the current rendered frame remains visible exactly as it was — especially the current subtitle line.

Target experience:

1. Press the normal **Menu / Start** button.
2. Gameplay, dialogue, or an in-engine cutscene freezes.
3. **No pause-menu overlay, darkening layer, replacement screen, OCR overlay, or external application appears.**
4. The current frame, HUD and subtitle remain visible for as long as needed.
5. Press **B** to resume, or press **Menu / Start** again to deliberately open KCD2's normal pause menu.

The normal pause menu is a **secondary action**, not the first screen shown when pausing.

## Core invariants

A correct implementation must:

- preserve the visible frame while paused;
- preserve the current subtitle whenever the game itself permits it;
- work in normal gameplay, dialogue and in-engine cutscenes;
- show no custom UI merely to implement pause;
- keep the untouched vanilla KCD2 pause menu available;
- keep ordinary Xbox-controller input working in the front-end menu and in game;
- never globally replace or clear KCD2's existing action maps;
- never require persistent controller remapping;
- fail safely back to vanilla behaviour if its compatibility checks fail.

## Target platform

Primary target:

- PC version distributed through **Xbox Store / Xbox app / Game Pass**;
- Xbox controller.

Other PC storefronts can be supported later if the implementation is portable.

## Non-goals

This project is not intended to become:

- a subtitle OCR/translation application;
- an external overlay;
- a dialogue-history tool;
- a replacement pause-menu UI;
- a general keybinding framework;
- a gameplay speed-control mod.

The feature should remain small and native-feeling.

## Desired controller UX

```text
Running game
    |
    +-- Menu / Start --> Clean Pause
                         |
                         +-- B -----------> Running game
                         |
                         +-- Menu / Start -> Vanilla KCD2 pause menu
```

No extra controller shortcut is introduced.

## Current status

**Experimental action-filter prototype; no supported release yet.**

Research established that KCD2's vanilla pause action is `ui_start_pause`. CryEngine action filters are evaluated before actions are dispatched, so the current prototype blocks that semantic action while allowing a separate `clean_pause_start` action on the same physical Xbox Menu/Start input.

```text
physical xi_start
  |
  +-- ui_start_pause       -> blocked before vanilla UI handler
  |
  +-- clean_pause_start    -> Game.PauseGame(true)
```

While clean-paused:

```text
B            -> Game.PauseGame(false)
Menu / Start -> real MenuEvents.DisplayIngameMenu(true)
```

The implementation uses native `Game.PauseGame(true)` rather than `t_scale 0` for the first retail test. This should pause game subsystems more coherently, but subtitle persistence and exact audio/cutscene behavior still require testing in the shipped game.

### Fail-closed input bootstrap

`ActionMapManager.LoadFromXML()` changes the action-map manager's profile version, so the mod does not load a guessed profile version.

At runtime it:

1. reads the effective `Libs/Config/defaultProfile.xml` through `System.LoadTextFile`;
2. extracts its version;
3. loads the packaged `cleanPauseProfile_v22.xml` only if the effective version is exactly `22`;
4. verifies the custom filters before enabling interception;
5. otherwise leaves vanilla controls untouched.

The vanilla Start action is also scoped to gameplay. It is not blocked in the front-end/main menu or while KCD2's existing `only_ui` filter owns menu input.

### Forbidden old approach

An old throwaway prototype called `ActionMapManager.InitActionMaps()` and disabled all Xbox-controller input, including the initial menu. That API clears the existing action-map/input configuration and is permanently forbidden in this project.

No prototype ZIP made before this repository is a supported release.

## What still requires a retail test

Static/source verification cannot prove the visual and subsystem behavior of the Xbox Store retail build. The decisive acceptance checks are:

- controller navigation remains normal in the initial/front-end menu;
- first gameplay Menu/Start reaches Clean Pause with **zero visible pause-menu frame**;
- current subtitle remains visible indefinitely;
- native pause stops dialogue/cutscene/audio progression coherently;
- B resumes while natively paused;
- second Menu/Start opens the untouched vanilla pause menu;
- dialogue/cutscene action-filter contexts still allow the custom Start/B actions.

See [docs/TESTING.md](docs/TESTING.md) for the exact matrix.

## Documentation

- [docs/DESIGN.md](docs/DESIGN.md) — state model and architectural constraints;
- [docs/FILTER_PROTOTYPE.md](docs/FILTER_PROTOTYPE.md) — current deterministic input architecture;
- [docs/ROOT_VERSION_RESEARCH.md](docs/ROOT_VERSION_RESEARCH.md) — version-safe supplemental-profile loading;
- [docs/RESEARCH.md](docs/RESEARCH.md) — confirmed API findings and discarded approaches;
- [docs/TESTING.md](docs/TESTING.md) — retail test procedure and release gate.

## Repository layout

```text
mod/
  mod.manifest
src/
  Libs/Config/cleanPauseProfile_v22.xml
  Scripts/Mods/clean_pause.lua
tools/
  build.py
  probe_profile_version.py
docs/
  DESIGN.md
  FILTER_PROTOTYPE.md
  ROOT_VERSION_RESEARCH.md
  RESEARCH.md
  TESTING.md
```

## Development build

Requires Python 3:

```bash
python tools/build.py
```

Creates:

```text
release/clean_pause/
  mod.manifest
  Data/clean_pause.pak
```

Validate a generated build with:

```bash
python tools/build.py --check
```

GitHub Actions also checks Lua 5.1 syntax, input-safety invariants, the XML action/filter contract, and generated PAK structure. Development artifacts are not treated as releases until retail acceptance passes.
