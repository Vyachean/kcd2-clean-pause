# KCD2 Clean Pause

A small mod for **Kingdom Come: Deliverance II** whose primary goal is to provide a real pause that does **not cover or replace the current game image**.

## Goal

When the player pauses, the game should stop while the current rendered frame remains visible exactly as it was — especially the current subtitle line.

The target experience is:

1. Press the normal **Menu / Start** button.
2. Gameplay, dialogue, or an in-engine cutscene freezes.
3. **No pause-menu overlay, darkening layer, replacement screen, OCR overlay, or external application appears.**
4. The current frame, HUD, and subtitle remain visible so the player can read them for as long as needed.
5. From this clean-pause state, the player must still be able to either resume or deliberately enter KCD2's normal pause menu.

The normal pause menu is therefore a **secondary action**, not the first thing shown when pausing.

## Core invariants

A correct implementation must:

- preserve the visible game frame while paused;
- preserve the current subtitle whenever the game itself is capable of doing so;
- work during normal gameplay as well as dialogue and in-engine cutscenes;
- avoid displaying custom UI merely to implement the pause;
- keep access to the vanilla KCD2 pause menu;
- keep ordinary Xbox-controller input working in the main menu and in game;
- never globally replace or clear KCD2's existing action maps at runtime;
- restore the previous game time scale/state when resuming rather than blindly forcing a default value;
- fail safely: if the mod cannot establish its input hook, vanilla controls must continue to work.

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

The feature should remain as small and native-feeling as possible.

## Desired controller UX

The preferred interaction is:

```text
Running game
    │
    └─ Menu / Start ──> Clean Pause
                         │
                         ├─ Resume action ──> Running game
                         │
                         └─ Menu / Start ──> Vanilla KCD2 pause menu
```

The exact resume button is intentionally not fixed yet. It should be chosen only after the vanilla pause action can be intercepted safely without breaking existing controller mappings.

## Current status

**Research / prototype stage. There is no supported release yet.**

Previous throwaway prototypes established that changing `t_scale` is a promising way to freeze game simulation while leaving the renderer active, but controller integration must be designed more carefully. In particular, calling `ActionMapManager.InitActionMaps()` from a mod is unsafe because it clears/reinitializes the game's existing action maps and can disable normal controller input.

The repository contains a deliberately safe state-controller skeleton, but **no controller hook is installed yet**. The unresolved task is to consume KCD2's existing vanilla pause action before it opens the pause menu.

See:

- [docs/DESIGN.md](docs/DESIGN.md) — target state model and architectural constraints;
- [docs/RESEARCH.md](docs/RESEARCH.md) — confirmed findings, discarded prototypes and open questions;
- [docs/TESTING.md](docs/TESTING.md) — retail acceptance matrix and safety gate.

## Repository layout

```text
mod/
  mod.manifest                 Development manifest
src/
  Scripts/Mods/clean_pause.lua Safe clean-pause state controller; no input remapping
tools/
  build.py                     Reproducible development PAK builder
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

This creates:

```text
release/clean_pause/
  mod.manifest
  Data/clean_pause.pak
```

Validate an existing generated build with:

```bash
python tools/build.py --check
```

Generated releases are intentionally ignored by Git until there is a tested release process.
