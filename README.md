# KCD2 Clean Pause

A small mod for **Kingdom Come: Deliverance II** whose primary goal is to provide a real pause that does **not cover or replace the current game image**.

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
- fail safely back to vanilla behaviour if its hook/bridge is unavailable.

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

**Experimental prototype; no supported release yet.**

Research has identified the exact KCD2 player actions:

```text
ui_start_pause
ui_back
```

The current prototype wraps the existing `Player.OnAction` handler and attempts to turn the normal first pause invocation into a clean native pause without changing any controller mapping.

The current approach is:

```text
ui_start_pause
  -> synchronously close the vanilla ingame menu through
     MenuEvents.DisplayIngameMenu(false)
  -> Game.PauseGame(true)
  -> use the game's existing only_ui input filter
  -> keep the rendered game frame visible
```

While clean-paused:

```text
ui_back        -> resume
ui_start_pause -> open the real vanilla pause menu
```

The prototype intentionally contains **no `ActionMapManager.InitActionMaps()` call, custom controller action map, `defaultProfile.xml` replacement, or `Menu.gfx` replacement.**

The remaining decisive questions can only be answered in the retail Xbox Store build:

- does KCD2 expose `MenuEvents.DisplayIngameMenu` under the inherited CryEngine name;
- is `Player.OnAction` ordered such that the pause menu can be cancelled before a frame is rendered;
- does `Game.PauseGame(true)` keep the current subtitle visible;
- does it stop dialogue audio/cutscene progression coherently;
- does B reliably reach `ui_back` while clean-paused.

If a menu appears for even one rendered frame, this pure-Lua interception point is not sufficient for the final zero-overlay requirement. The next experiment will be a pause-aware zero-delay finalizer; if that still flashes, the correct fallback is a narrow native hook for `ui_start_pause`, not controller remapping.

## Safety history

An old throwaway prototype called `ActionMapManager.InitActionMaps()` and disabled all Xbox-controller input, including the initial menu. That API clears the existing action-map/input configuration and is permanently forbidden in this project.

No prototype ZIP made before this repository is a supported release.

## Documentation

- [docs/DESIGN.md](docs/DESIGN.md) — state model and current native-pause/menu-bridge architecture;
- [docs/RESEARCH.md](docs/RESEARCH.md) — confirmed API findings, source references and discarded approaches;
- [docs/TESTING.md](docs/TESTING.md) — exact retail test procedure and release gate.

## Repository layout

```text
mod/
  mod.manifest
src/
  Scripts/Mods/clean_pause.lua  Experimental pure-Lua implementation
tools/
  build.py                      Reproducible development PAK builder
docs/
  DESIGN.md
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

Generated builds are intentionally ignored by Git until the retail behaviour above is proven.
