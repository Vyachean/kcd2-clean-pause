# Official-mod reference evidence

This note records the evidence behind the current `.pak`/Lua implementation.

## Warhorse mod structure

Warhorse's KCD2 Modding Wiki documents `mod.manifest`, `Data/*.pak` mirroring base-game paths, `Scripts/Mods/<modid>.lua` as a mod bootstrap, and whole-file override behaviour when multiple mods provide the same data path.

Mirror:

- https://github.com/muyuanjin/kcd2-mod-docs/tree/main/official-wiki

## Xbox/Game Pass normal-mod location

Current KCD2 Vortex support and Xbox-specific Nexus instructions place normal mods in `%USERPROFILE%\Documents\kingdomcome_mods`, not beside `KingdomCome.exe`.

## Retail profile evidence

KCD2 1.5.6's effective profile has two separate Start routes:

```xml
<actionmap name="open_menu" ...>
  <action name="open_menu" ... xboxpad="xi_start" ... />
</actionmap>

<actionmap name="open_pause_menu" ...>
  <action name="open_pause_menu" ... xboxpad="xi_start" ... />
</actionmap>
```

Dialogue and cutscene maps include `open_pause_menu`; ordinary gameplay includes `open_menu`.

## Packaged `consoleCmd` actions

KCD2 action profiles support `consoleCmd="1"`. Existing controller quicksave/keybind mods use the same profile mechanism, including `xi_start`.

Implication: receiving Start does not itself require native code. PR #2 only disproved a **runtime supplemental** Start map on the tested Xbox build.

## Retail pause API

Warhorse ScriptBind docs expose `Game.PauseGame(bool)` and retail KCD2 scripts call `Game.PauseGame(true)`.

## Retail ActionMapManager API

Warhorse's retail method list includes `EnableActionMap` and `IsFilterEnabled`, but not `EnableActionFilter`.

Reference:

- https://github.com/muyuanjin/kcd2-mod-docs/blob/main/script_bind_2025_01_14/!!MEMBERTYPE_Methods_CScriptBind_ActionMapManager.html

## KCD2 1.5.6 priority/exclusivity evidence

`libKCD2` reverse engineering identifies `m_priority`, `m_exclusivity`, `Enable`, `GetPriority` and `GetExclusivity` on the retail 1.5.6 `IActionMap` object.

Reference:

- https://github.com/JerryYOJ/libKCD2/blob/master/include/Offsets/vtables/IActionMap.h

The game's own profile uses this model for mutually exclusive gameplay, dialogue, cutscene, menu and overlay contexts. Clean Pause therefore uses an overlay-priority exclusive temporary map.

## `UIAction.CallFunction`

Warhorse documents `UIAction.CallFunction(elementName, instanceID, functionName, ...)` and explicitly permits `elementName` to identify a C++ UIEventSystem.

Reference:

- https://github.com/muyuanjin/kcd2-mod-docs/blob/main/script_bind_2025_01_14/CScriptBind_UIAction__CallFunction@IFunctionHandler_@char_@int@char_.html

## `MenuEvents.DisplayIngameMenu(bool)` reference

CryEngine GameSDK registers a UI-to-system event system `MenuEvents` with `DisplayIngameMenu(bool)`. Its normal open path pauses the game, enables `only_ui`, and emits the real ingame-menu UI event.

Reference:

- https://github.com/MergHQ/CRYENGINE/blob/release/Code/GameSDK/GameDll/UI/UIMenuEvents.cpp

The current implementation calls:

```lua
UIAction.CallFunction("MenuEvents", -1, "DisplayIngameMenu", true)
```

**without first unpausing**. The exact event-system name still requires direct retail KCD2 1.5.6 confirmation.

## Whole-file compatibility cost

Warhorse recommends granular patch formats where they exist, but no official granular patch format is documented for `defaultProfile.xml`.

Consequently the builder reads the exact installed profile and patches it locally instead of shipping a copied profile. This avoids a stale-profile mismatch but not conflicts with another mod replacing the same file.

## Current conclusion

The official path has enough documented/observed capability to deserve a complete retail test before native code is considered necessary. Remaining unknowns are subtitle retention, input isolation semantics, retail `MenuEvents` availability, and coherent audio/cutscene pause/resume.
