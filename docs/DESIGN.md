# Design

## Product contract

Clean Pause must stop gameplay/dialogue/in-engine-cutscene progression while leaving the current rendered frame unobscured.

Controller state model:

```text
Running
  Start -> CleanPaused

CleanPaused
  B     -> Running
  Start -> VanillaMenu
```

`VanillaMenu` is KCD2's real pause menu. Clean Pause never draws a replacement UI.

## Chosen implementation path

The primary implementation is a normal KCD2 `.pak` mod. Native DLL/ASI code is fallback-only.

The exact Xbox Store 1.5.6 retail profile established that Start is not one universal action:

- normal gameplay includes `open_menu`, whose action `open_menu` is bound to `xi_start`;
- dialogue, cutscenes and standard minigame contexts include `open_pause_menu`, whose action `open_pause_menu` is bound to `xi_start`.

The builder patches **both existing actions**, preserving their names and bindings, and makes them `onPress="1" consoleCmd="1"`. Removing their original `onRelease` prevents one physical Start press from invoking Clean Pause twice.

Keeping the original action IDs is important because existing KCD2 action filters and user binding data continue to refer to the same semantic actions.

## Temporary controls map

The patched profile adds one map:

```xml
<actionmap name="clean_pause_controls"
           priority="overlays"
           exclusivity="1">
```

It is disabled outside Clean Pause.

The choice is intentional:

- retail KCD2 action maps have an explicit integer priority and exclusivity flag;
- dialogue/cutscene/menu/overlay maps already use this mechanism for contextual input isolation;
- `overlays` is above gameplay/minigame/cutscene/menu priorities but still below platform-interrupt priorities.

The map owns:

```text
Start press -> clean_pause_open_menu
B press     -> clean_pause_block_b_press
B release   -> clean_pause_resume
```

B resumes on release so the complete B press/release cycle stays in the Clean Pause context and cannot become `dialog_skip`, `cutscene_skip`, etc.

## Enter Clean Pause

A retail `open_menu` or `open_pause_menu` console command calls `CleanPause.OnPauseAction()`.

Entry succeeds only when:

- the mod state is `running`;
- an in-game player exists;
- vanilla `only_ui` is not already active;
- the temporary controls map can be enabled;
- `Game.PauseGame(true)` succeeds.

Then state becomes `clean_paused`.

The mod does not open and then hide the vanilla menu. Therefore, if routing works, there is no intentional menu frame to flash.

## Resume

`clean_pause_resume` fires on B release:

1. disable `clean_pause_controls`;
2. call `Game.PauseGame(false)`;
3. return to `running`.

If unpause fails, the controls map is re-enabled and Clean Pause retains ownership.

## Vanilla-menu handoff

Second Start uses `clean_pause_open_menu` from the temporary map:

1. disable `clean_pause_controls`;
2. keep the game paused;
3. call `UIAction.CallFunction("MenuEvents", -1, "DisplayIngameMenu", true)`;
4. if successful, relinquish Clean Pause ownership.

There is deliberately no `PauseGame(false) -> Start -> PauseGame(true)` transition.

Warhorse documents `UIAction.CallFunction` as able to invoke a C++ UIEventSystem. CryEngine's matching `MenuEvents` implementation exposes `DisplayIngameMenu(bool)` and owns the normal forced-pause / `only_ui` lifecycle. The exact event-system name still requires retail KCD2 verification.

## Existing actionPass filters

Retail Lua does not expose `ActionMapManager.EnableActionFilter`, so Clean Pause does not create or toggle its own filter.

Instead, the builder examines the installed profile. If an existing `actionPass` filter already permits `open_menu` or `open_pause_menu`, the builder also permits:

- `clean_pause_open_menu`;
- `clean_pause_block_b_press`;
- `clean_pause_resume`.

`actionFail` filters are not modified. Thus any restriction that prevents the original pause action continues to prevent entering Clean Pause.

## Whole-file profile compatibility

Warhorse's normal mod system can override `Libs/Config/defaultProfile.xml`, but there is no official granular merge format for this file. Therefore the test builder:

- reads the target installation's exact profile from `IPL_GameData.pak`;
- changes only the required action tags/filter allow-lists;
- packages that exact patched file into the mod;
- refuses to guess if the expected retail structure is absent.

This reduces version mismatch but does not eliminate conflicts with another mod that also replaces `defaultProfile.xml`.

## Forbidden paths

- `ActionMapManager.InitActionMaps()` — observed to destroy controller/action-map state in an earlier prototype;
- runtime supplemental Start map via `LoadFromXML()` — failed twice on Xbox Store 1.5.6;
- runtime `EnableActionFilter()` — not present in the retail Lua surface used by the target;
- `Player.OnAction` replacement;
- native input hook unless the official path is proven insufficient;
- `Menu.gfx` replacement;
- external overlay/OCR.

## Remaining runtime gates

The design remains a test candidate until retail proves:

- zero visible pause-menu frame;
- subtitle persistence under `Game.PauseGame(true)`;
- input isolation from the exclusive overlay-priority map;
- B resume without dialogue/cutscene side effects;
- real vanilla-menu handoff through `MenuEvents`;
- coherent audio/cutscene pause and resume.
