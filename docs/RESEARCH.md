# Research notes

This file separates confirmed KCD2 facts from behaviours that still require retail testing.

## Confirmed: official mod structure

Warhorse documents normal mods as `mod.manifest` plus `Data/*.pak`. A mod PAK mirrors the game's data paths and may contain `Scripts/Mods/<modid>.lua`, which is executed as the mod's Lua bootstrap.

Official structure reference:

- https://github.com/muyuanjin/kcd2-mod-docs/tree/main/official-wiki

For the Xbox Store / Game Pass build, current Nexus/Vortex support places normal mods under `%USERPROFILE%\Documents\kingdomcome_mods` rather than the game install directory.

## Confirmed: retail 1.5.6 Start routes

The effective retail `defaultProfile.xml` uses:

```xml
<actionmap name="open_menu" ...>
  <action name="open_menu" ... xboxpad="xi_start" ... />
</actionmap>

<actionmap name="open_pause_menu" ...>
  <action name="open_pause_menu" ... xboxpad="xi_start" ... />
</actionmap>
```

Normal player gameplay includes `open_menu`. Dialogue, cutscene and standard minigame maps include `open_pause_menu`.

This supersedes the earlier assumption that one `ui_start_pause` action was the retail controller route for every context.

## Confirmed: packaged console-command actions are supported

KCD2 profiles support `consoleCmd="1"` on an action input. Existing KCD2 mods use this for hotkeys, including controller bindings.

The official-only implementation therefore patches the already-existing retail Start actions rather than adding a competing Start action at runtime.

## Confirmed: `Game.PauseGame(bool)`

Warhorse ScriptBind documentation defines:

```lua
Game.PauseGame(true)
Game.PauseGame(false)
```

and retail scripts use `Game.PauseGame(true)`. This is the preferred pause primitive.

Reference: `script_bind_2025_01_14/CScriptBind_Game__PauseGame...` in `muyuanjin/kcd2-mod-docs`.

Whether it preserves the currently rendered subtitle is a product-level runtime question, not an API-existence question.

## Confirmed: retail ActionMapManager Lua surface

The Warhorse retail ScriptBind method list exposes, among others:

- `EnableActionMap`;
- `EnableActionMapManager`;
- `IsFilterEnabled`;
- `InitActionMaps`;
- `LoadFromXML`;
- `SetActionListener`.

It does **not** list `EnableActionFilter`. The previous PR #4 implementation that called `ActionMapManager.EnableActionFilter(...)` was therefore not acceptable for the retail target and has been removed.

Reference: `script_bind_2025_01_14/!!MEMBERTYPE_Methods_CScriptBind_ActionMapManager.html`.

## Confirmed: KCD2 1.5.6 action-map priority/exclusivity exists

`libKCD2` reverse engineering for `WHGame.dll 1.5.6` recovers KCD2's `IActionMap` object layout and vtable, including `m_exclusivity`, integer `m_priority`, `Enable(bool)`, `GetPriority()` and `GetExclusivity()`.

Reference:

- https://github.com/JerryYOJ/libKCD2/blob/master/include/Offsets/vtables/IActionMap.h

The retail profile itself consistently uses higher-priority exclusive maps for dialogue, cutscenes, menus and overlays. This is the basis for `clean_pause_controls` using `priority="overlays" exclusivity="1"`.

The exact observed suppression behaviour of this new map remains part of retail acceptance.

## Confirmed: `UIAction.CallFunction` can target a UIEventSystem

Warhorse documents `UIAction.CallFunction(elementName, instanceID, functionName, ...)` and states that `elementName` may be a UI element or a C++ UIEventSystem name.

Reference: `script_bind_2025_01_14/CScriptBind_UIAction__CallFunction...` in `muyuanjin/kcd2-mod-docs`.

## Reference: CryEngine `MenuEvents.DisplayIngameMenu`

The matching CryEngine GameSDK registers a `MenuEvents` UI-to-system event named `DisplayIngameMenu(bool)`.

Opening the menu in that reference implementation calls forced game pause, enables `only_ui`, and emits the real ingame-menu start event.

Reference:

- https://github.com/MergHQ/CRYENGINE/blob/release/Code/GameSDK/GameDll/UI/UIMenuEvents.cpp

This is strong evidence for the handoff, but the exact `MenuEvents` name has not yet been confirmed by an Xbox Store 1.5.6 runtime test.

## Confirmed failure: `InitActionMaps()`

An earlier prototype called `ActionMapManager.InitActionMaps()` with a partial profile. Observed on the target game: Xbox-controller input stopped working globally, including the initial menu.

Permanent rule: **never call `InitActionMaps()` from Clean Pause.**

## Confirmed failure: supplemental runtime Start map

PR #2 used `ActionMapManager.LoadFromXML()` to add a separate `xi_start` action and a safe handshake before interception.

Two Xbox Store 1.5.6 tests produced the same result: controller stayed operational, custom Start never fired, vanilla Start remained vanilla.

Conclusion: do not return to a competing supplemental Start binding.

## Why the current builder uses the installed profile

Warhorse's official mod system replaces files by path. There is no official patch/merge format for `defaultProfile.xml`; if two mods supply it, load order decides which whole file wins.

Therefore the repository does not bundle a copied retail profile. `tools/build_from_game.py` reads the installed `Data/IPL_GameData.pak`, verifies the expected 1.5.6 routes, patches only those entries, and emits the test mod.

## Current runtime questions

1. Does first Start produce zero menu flash?
2. Does `Game.PauseGame(true)` leave the current subtitle visible indefinitely?
3. Does the active overlay-priority exclusive map suppress lower gameplay/dialogue/cutscene actions while still delivering its own Start/B actions?
4. Does B release resume without a dialogue/cutscene skip side effect?
5. Does `UIAction.CallFunction("MenuEvents", -1, "DisplayIngameMenu", true)` open the real retail pause menu?
6. Does closing that menu resume normally rather than restoring Clean Pause?
7. Are speech audio, camera, animation and scripted progression stopped coherently?

These are the next retail tests; they are not reasons to add native code pre-emptively.
