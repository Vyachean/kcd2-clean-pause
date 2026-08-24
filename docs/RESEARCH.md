# Research notes

This file separates confirmed KCD2 facts from behaviours that still require retail testing.

## Confirmed: official mod structure

Warhorse documents normal mods as `mod.manifest` plus `Data/*.pak`. A mod PAK mirrors game data paths and may contain `Scripts/Mods/<modid>.lua`, which is executed as the mod Lua bootstrap.

Official structure reference:

- https://github.com/muyuanjin/kcd2-mod-docs/tree/main/official-wiki

For Xbox Store / Game Pass, normal mods are installed under `%USERPROFILE%\Documents\kingdomcome_mods`.

## Confirmed: retail 1.5.6 pause routes

The extracted target `defaultProfile.xml` contains:

```xml
<actionmap name="open_menu" ...>
  <action name="open_menu"
          keyboard="_keybinds_ref_"
          xboxpad="xi_start"
          pspad="pad_start" ... />
</actionmap>

<actionmap name="open_pause_menu" ...>
  <action name="open_pause_menu"
          keyboard="_keybinds_ref_"
          xboxpad="xi_start"
          pspad="pad_start" ... />
</actionmap>
```

Normal gameplay includes `open_menu`. Dialogue, cutscene and standard minigame contexts include `open_pause_menu`.

The same retail profile also demonstrates explicit keyboard input names such as `keyboard="escape"`, so a custom action can bind Escape directly while the original vanilla action retains `_keybinds_ref_`.

## Confirmed: KCD2 console-command attribute is `consoleCMD`

KCD2 keybind/superaction examples use exact:

```xml
<action consoleCMD="1" ... />
```

`v0.1.0-rc.1` incorrectly emitted `consoleCmd="1"`, following generic CryEngine documentation instead of KCD2's actual keybind convention.

XML attribute names are case-sensitive. Retail rc1 behaviour was decisive:

- Escape stopped pausing;
- Xbox Start stopped pausing;
- Clean Pause did not run.

The patcher, pinned release source, unit tests and CI now require `consoleCMD="1"` and reject `consoleCmd="1"`.

KCD2 references include the `muyuanjin/kcd2-mod-docs` modding notes and community KCD2 keybind/superaction examples.

## Confirmed: rc1 also exposed an unsafe replacement design

The casing bug alone explains why the custom command did not execute, but rc1 should still not have been able to remove pause entirely.

The old design converted the only retail `open_menu` / `open_pause_menu` actions into custom console actions. If custom execution failed, no vanilla route remained.

The rc2 design therefore preserves each original semantic action as **release-only vanilla fallback** and adds a separate **press-only custom console action**:

```text
press
  -> clean_pause_enter_gameplay / clean_pause_enter_pause_context
  -> consoleCMD

release
  -> original open_menu / open_pause_menu
  -> vanilla fallback
```

If custom entry succeeds, it enables the exclusive `clean_pause_controls` map before release. That map contains `clean_pause_block_start_release`, which consumes the release and prevents a vanilla menu flash.

If custom entry fails, the controls map is never enabled and the original release reaches vanilla pause. This is the new fail-safe invariant.

Whether KCD2 dispatches the custom press exactly as expected still requires retail testing; static CI proves only that both independent routes are present in the actual release PAK.

## Confirmed: retail pause restrictions must be mirrored

The exact target profile contains an `actionFail` filter named `no_menu` that blocks `open_menu`.

Because the new custom press action has a different semantic name, failing to mirror this filter would allow Clean Pause in contexts where vanilla pause is forbidden.

The patcher therefore adds `clean_pause_enter_gameplay` wherever `open_menu` is blocked, and similarly mirrors `open_pause_menu` restrictions. For `actionPass` filters it also allow-lists the temporary Clean Pause controls.

The exact Xbox Store 1.5.6 profile contains no `actionPass` filters.

## Confirmed: `System.AddCCommand`

KCD2 exposes:

```lua
System.AddCCommand(name, luaCode, description)
```

and `Scripts/Mods/<modid>.lua` is a supported mod bootstrap path. Clean Pause registers `clean_pause_enter_gameplay`, `clean_pause_enter_pause_context`, `clean_pause_open_menu` and `clean_pause_resume` through this API.

Retail rc2 still has to prove execution through the corrected profile route.

## Confirmed: `Game.PauseGame(bool)`

Warhorse ScriptBind documentation and KCD2 API exports include:

```lua
Game.PauseGame(true)
Game.PauseGame(false)
```

This remains the preferred pause primitive. Subtitle/frame retention under it is a runtime product question.

## Confirmed: retail ActionMapManager Lua surface

The Warhorse retail ScriptBind method list exposes, among others:

- `EnableActionMap`;
- `EnableActionMapManager`;
- `IsFilterEnabled`;
- `InitActionMaps`;
- `LoadFromXML`;
- `SetActionListener`.

It does **not** list `EnableActionFilter`. Clean Pause does not use that unavailable API.

## Confirmed: KCD2 1.5.6 action-map priority/exclusivity exists

`libKCD2` reverse engineering for `WHGame.dll 1.5.6` recovers `m_exclusivity`, integer `m_priority`, `Enable(bool)`, `GetPriority()` and `GetExclusivity()`.

The retail profile uses the same mechanism for contextual input isolation. This supports `clean_pause_controls` using:

```text
priority="overlays"
exclusivity="1"
```

The exact suppression behaviour of the new map remains a retail acceptance item.

## Confirmed: `UIAction.CallFunction` can target a UIEventSystem

Warhorse documents `UIAction.CallFunction(elementName, instanceID, functionName, ...)` and states that `elementName` may be a UI element or C++ UIEventSystem name.

The matching CryEngine GameSDK exposes `MenuEvents.DisplayIngameMenu(bool)`, which owns forced pause / UI-only behaviour there.

This is strong evidence for the second-Start handoff, but exact KCD2 exposure of `MenuEvents` remains unconfirmed at runtime.

## Confirmed failures

### `v0.1.0-rc.1`

Observed on Xbox Store 1.5.6:

- Escape did not pause;
- Xbox Start did not pause;
- Clean Pause did not activate.

Root cause: wrong-case `consoleCmd` plus absence of a vanilla fallback route.

### `InitActionMaps()` prototype

An earlier prototype called `ActionMapManager.InitActionMaps()` with a partial profile. Xbox-controller input stopped working globally, including the initial menu.

Permanent rule: **never call `InitActionMaps()` from Clean Pause.**

### Supplemental runtime Start map

PR #2 used runtime `LoadFromXML()` to add a competing `xi_start` action. Two retail tests kept controller input operational but the custom Start never fired and vanilla Start remained vanilla.

Do not return to that design.

## Versioned release source

KCD2's official file override is last-mod-wins for `defaultProfile.xml`; there is no official granular merge format for it.

For KCD2 1.5.6 the repository versions the reviewed patched target profile under `vendor/kcd2/xbox-1.5.6/` as deterministic gzip+base64 text.

Original retail profile SHA-256:

```text
69ad9fd618cd31961fef8eb061f3f2723997df5e0fb257ec74d0d5f555592565
```

Current fail-safe patched profile SHA-256:

```text
9838db3747f7f36e0c9c281b8770bc7300998515407515b65493b8e9a9bcd14e
```

`tools/build_release.py` verifies both the digest and the semantic fail-safe contract before packaging.

## Current runtime questions for rc2

1. Does exact `consoleCMD` execute the registered custom command on Escape and Xbox Start press?
2. Does successful entry activate `clean_pause_controls` early enough to consume the same release?
3. If custom execution still fails, does the original release-only action reliably open vanilla pause?
4. Does first successful Clean Pause produce zero vanilla menu flash?
5. Does `Game.PauseGame(true)` leave the current subtitle visible indefinitely?
6. Does the exclusive controls map suppress lower gameplay/dialogue/cutscene actions?
7. Does B release resume without skip/cancel side effects?
8. Does `MenuEvents.DisplayIngameMenu(true)` open the real retail pause menu on second Start/Escape?
9. Are speech audio, camera, animation and scripted progression stopped/resumed coherently?

These questions require retail observation; they are not statically assumed to be solved.
