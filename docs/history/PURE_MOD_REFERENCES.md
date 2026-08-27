# Official-mod reference evidence

> **Status: historical research.** This note records evidence gathered while the project was still evaluating a pure `.pak`/Lua implementation. The current production mod is native; see [DESIGN.md](DESIGN.md). Statements below describe capabilities and experiments, not the active architecture.

## Warhorse mod structure

Warhorse's KCD2 Modding Wiki documents `mod.manifest`, `Data/*.pak` mirroring base-game paths, `Scripts/Mods/<modid>.lua` as a mod bootstrap, and whole-file override behaviour when multiple mods provide the same data path.

Mirror:

- https://github.com/muyuanjin/kcd2-mod-docs/tree/main/official-wiki

## Xbox/Game Pass normal-mod location

KCD2 Vortex support and Xbox-specific Nexus instructions place normal `.pak` mods in `%USERPROFILE%\Documents\kingdomcome_mods`, not beside `KingdomCome.exe`.

This evidence was relevant to the discarded pure-mod path. The current native editions install beside the game executable / `WHGame.dll` instead.

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

Historical implication: receiving Start did not itself require native code. Retail testing nevertheless showed that a supplemental action-map route was not a reliable ownership mechanism for Clean Pause on the target build.

## Retail pause API research

Warhorse ScriptBind documentation exposes pause-related bindings, and retail scripts contain pause calls. Later testing established that a custom Lua pause/freeze route was still insufficient for Clean Pause because it did not reproduce the complete vanilla pause lifecycle.

The current production design therefore does not use a custom Lua/native `PauseGame` owner.

## Retail ActionMapManager API

Warhorse's retail method list includes action-map/filter inspection and control APIs. These were investigated for custom input isolation.

Reference:

- https://github.com/muyuanjin/kcd2-mod-docs/blob/main/script_bind_2025_01_14/!!MEMBERTYPE_Methods_CScriptBind_ActionMapManager.html

## KCD2 1.5.6 priority/exclusivity evidence

`libKCD2` reverse engineering identifies priority/exclusivity state on retail 1.5.6 action-map objects.

Reference:

- https://github.com/JerryYOJ/libKCD2/blob/master/include/Offsets/vtables/IActionMap.h

This supported the historical action-map prototype but is no longer part of the active Clean Pause ownership model.

## `UIAction.CallFunction` / `MenuEvents` research

Warhorse and CryEngine references showed that UI event systems can be invoked from scripts and motivated an experiment around `MenuEvents.DisplayIngameMenu(bool)`.

References:

- https://github.com/muyuanjin/kcd2-mod-docs/blob/main/script_bind_2025_01_14/CScriptBind_UIAction__CallFunction@IFunctionHandler_@char_@int@char_.html
- https://github.com/MergHQ/CRYENGINE/blob/release/Code/GameSDK/GameDll/UI/UIMenuEvents.cpp

That route is not used in production. Current Clean Pause forwards the real Escape/Start event and lets KCD2 establish its own menu/pause state.

## Whole-file compatibility cost

The historical profile-builder work also established that replacing `defaultProfile.xml` carries whole-file compatibility risk when another mod changes the same path.

That compatibility cost is another reason the current mod avoids profile replacement entirely.

## Historical conclusion

The official `.pak`/Lua route was worth investigating because it exposed enough profile and scripting capability to build safe diagnostics. Retail evidence ultimately showed that it was the wrong ownership boundary for Clean Pause.

The retained value of this document is the evidence behind the rejection of profile/action-map/custom-pause ownership, not a recommendation to restore that implementation.
