# Pure-mod reference evidence

This note records concrete documentation and working-mod evidence relevant to implementing Clean Pause as a normal KCD2 `.pak` mod on PC Xbox Store / Xbox app / Game Pass.

## 1. Packaged keybinds are a normal KCD2 modding mechanism

`kcd2-mod-docs` explicitly lists hotkeys via `Libs/Config/defaultProfile.xml` using console-command actions as a stable Lua-layer pattern.

Independent KCD2 modding notes likewise identify `defaultProfile.xml` and `keybindSuperactions.xml` as the standard keybinding data files.

Implication: the core Clean Pause input path does not need a native DLL merely to receive a controller button. The earlier PR #2 failure was specific to runtime supplemental action-map loading, not to packaged keybinds in general.

## 2. Quicksave proves `xi_start` works in a normal packaged profile

Magus' Quicksave mod documents this working Xbox/PlayStation controller action:

```xml
<action name="MagusQuickSaveController"
        onHold="1"
        holdTriggerDelay="0.3"
        holdRepeatDelay="-1"
        xboxpad="xi_start"
        pspad="pad_start"
        consoleCmd="1" />
```

Recent user reports on the mod page confirm it works on KCD2 1.5 / 1.5.3. The author also confirms that conflicting key-changing mods must merge the relevant files.

Implication: Start/Menu can be routed to a Clean Pause console command through a normal `defaultProfile.xml` override. This is substantially stronger evidence than the failed `ActionMapManager.LoadFromXML()` prototype.

## 3. Retail Player.lua confirms the relevant semantic actions

The extracted KCD2 Player script contains:

```lua
function Player:OnAction(action, activation, value)
    -- ... for now got just ui_back, ui_start_pause
```

This independently confirms the semantic names `ui_back` and `ui_start_pause` in retail KCD2.

Do not infer from this alone that overriding `Player:OnAction` can suppress the vanilla pause menu; dispatch ordering remains a separate concern. The preferred pure-mod design avoids that problem by changing the packaged binding so the original pause action is not generated for the first Start press.

## 4. Existing pure-Lua menu mods handle Escape/B and menu state

KCD2 Native Menus Framework uses the Player Event Dispatcher helper so a custom Lua-driven menu can close via Escape / Xbox B. Its changelog also documents fixes around restoring normal character/map/inventory keybind behavior after a custom menu closes and preventing its menu from opening while other game menus are active.

Implication: B/Escape handling and menu-state lifecycle are established pure-mod patterns in KCD2. We should reuse the same conceptual lifecycle rather than inventing a controller remap.

## 5. `UIAction.CallFunction` can invoke a UIEventSystem

Warhorse's ScriptBind documentation defines:

```lua
UIAction.CallFunction(elementName, instanceID, functionName, [arg1], ...)
```

and explicitly states that `elementName` can be a UI element name **or a UIEventSystem name defined in C++**.

This is the preferred mechanism to investigate for the second Start transition from Clean Pause to the untouched vanilla pause menu.

## 6. CryEngine reference implementation exposes `MenuEvents.DisplayIngameMenu(bool)`

The matching CryEngine GameSDK implementation registers a UI event system named `MenuEvents` with a UI-to-system event:

```text
DisplayIngameMenu(bool Display)
```

Its reference behavior is:

- `true` -> pause the game, enable `only_ui`, emit `OnStartIngameMenu`;
- `false` -> unpause, disable `only_ui`, emit `OnStopIngameMenu`.

Therefore the most promising pure-Lua handoff candidate is:

```lua
Game.PauseGame(false)
UIAction.CallFunction("MenuEvents", -1, "DisplayIngameMenu", true)
```

This is **not yet proven in KCD2 retail** because the exact `MenuEvents` event-system name has not yet been observed directly in KCD2 1.5.6. It should be tested as a narrow runtime probe rather than assumed.

## 7. Retail pause primitive is documented

Warhorse exposes:

```lua
Game.PauseGame(true)
Game.PauseGame(false)
```

and retail scripts use `Game.PauseGame(true)` themselves.

This remains the preferred Clean Pause primitive. `t_scale` is fallback-only if retail testing shows that the native pause removes subtitles or otherwise violates the product requirement.

## 8. Compatibility cost of `defaultProfile.xml`

`defaultProfile.xml` and `keybindSuperactions.xml` are whole-file conflict points under normal KCD2 mod loading. Existing mods and community documentation explicitly require manual merge/load-order handling when multiple keybind mods replace the same files.

For the first Clean Pause release this is acceptable if:

- the patch against the vanilla 1.5.6 profile is minimal and documented;
- a manual merge snippet is provided;
- no unrelated bindings are changed.

## Current conclusion

The evidence supports continuing the pure `.pak` implementation. The remaining unknowns are narrow:

1. obtain or reproduce the exact effective 1.5.6 pause entries in `defaultProfile.xml`;
2. verify `UIAction.CallFunction("MenuEvents", -1, "DisplayIngameMenu", true)` on KCD2 1.5.6;
3. verify `Game.PauseGame(true)` leaves the current subtitle/frame visible.

A native DLL is not justified unless one of these pure-mod capabilities is disproven in retail testing.
