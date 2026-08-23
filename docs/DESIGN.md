# Design

## Product contract

Clean Pause must stop gameplay/dialogue/in-engine-cutscene progression while leaving the current rendered frame unobscured.

```text
Running
  Escape / Start -> CleanPaused

CleanPaused
  B              -> Running
  Escape / Start -> VanillaMenu
```

`VanillaMenu` is KCD2's real pause menu. Clean Pause never draws a replacement UI.

## Retail routes

Xbox Store 1.5.6 uses two semantic pause actions:

```text
normal gameplay              open_menu/open_menu
dialogue/cutscene/minigame   open_pause_menu/open_pause_menu
```

Both use `keyboard="_keybinds_ref_"`, `xboxpad="xi_start"` and `pspad="pad_start"` in the retail profile.

## rc1 failure and design correction

`v0.1.0-rc.1` changed the original pause actions into console actions and used the wrong attribute spelling `consoleCmd="1"`. KCD2 keybind actions require exact `consoleCMD="1"`.

Retail result:

- Escape stopped pausing;
- Xbox Start stopped pausing;
- Clean Pause did not execute.

The casing bug is fixed, but the more important correction is architectural: **Clean Pause no longer replaces the only vanilla pause route.**

## Fail-safe press/release split

For each retail pause action, the patcher now creates two routes on the same physical control.

### Press: custom Clean Pause

```text
open_menu map:
  clean_pause_enter_gameplay
    onPress=1
    keyboard=escape
    xboxpad=xi_start
    consoleCMD=1

open_pause_menu map:
  clean_pause_enter_pause_context
    onPress=1
    keyboard=escape
    xboxpad=xi_start
    consoleCMD=1
```

These command names are registered by the mod Lua bootstrap and call `CleanPause.OnPauseAction()`.

### Release: original vanilla fallback

The original actions remain in place with their original semantic names and retail bindings:

```text
open_menu/open_menu
open_pause_menu/open_pause_menu
```

They are changed to `onRelease="1"` only and are **not** console commands.

This creates the safety invariant:

```text
custom press works
  -> Clean Pause enables its exclusive controls map
  -> same release is consumed by that map
  -> vanilla menu stays hidden

custom press fails
  -> exclusive controls map never activates
  -> same release reaches original retail pause action
  -> vanilla pause menu opens
```

A bug in the custom Lua/command path should therefore degrade to vanilla pause rather than remove pause entirely.

The explicit custom keyboard binding is `escape`; the original fallback keeps `_keybinds_ref_`. Xbox Start remains `xi_start` on both routes.

## Temporary controls map

The patched profile adds:

```xml
<actionmap name="clean_pause_controls"
           priority="overlays"
           exclusivity="1">
```

It is disabled outside Clean Pause and contains exactly:

```text
Escape / Start press   -> clean_pause_open_menu       (consoleCMD)
Escape / Start release -> clean_pause_block_start_release
B press                -> clean_pause_block_b_press
B release              -> clean_pause_resume          (consoleCMD)
```

The Start/Escape release sink is essential to the fail-safe split: after successful Clean Pause entry, it prevents the original release-only vanilla action from firing.

B resumes on release so the complete B press/release cycle stays inside the Clean Pause context and cannot become `dialog_skip`, `cutscene_skip`, etc.

## Enter Clean Pause

`clean_pause_enter_gameplay` or `clean_pause_enter_pause_context` calls `CleanPause.OnPauseAction()`.

Entry succeeds only when:

- state is `running`;
- an in-game player exists;
- vanilla `only_ui` is not active;
- `clean_pause_controls` can be enabled;
- `Game.PauseGame(true)` succeeds.

Then state becomes `clean_paused` before the physical pause button is released, so the exclusive release sink owns that release.

## Resume

`clean_pause_resume` fires on B release:

1. disable `clean_pause_controls`;
2. call `Game.PauseGame(false)`;
3. return to `running`.

If unpause fails, the controls map is re-enabled and Clean Pause keeps ownership.

## Vanilla-menu handoff

Second Escape/Start currently uses `clean_pause_open_menu`:

1. disable `clean_pause_controls`;
2. keep the game paused;
3. call `UIAction.CallFunction("MenuEvents", -1, "DisplayIngameMenu", true)`;
4. on success, relinquish Clean Pause ownership;
5. on failure, re-enable the controls map and remain clean-paused.

There is no intermediate `PauseGame(false)` tick. The exact `MenuEvents` exposure remains a retail acceptance item.

## Filter preservation

Custom entry actions must obey the same contextual restrictions as the original pause actions.

For every `actionFail` filter containing `open_menu` or `open_pause_menu`, the patcher adds the corresponding custom entry action. This is important for the exact retail `no_menu` filter.

For an `actionPass` filter containing a retail pause action, the patcher adds:

- the corresponding custom entry action;
- `clean_pause_open_menu`;
- `clean_pause_block_start_release`;
- `clean_pause_block_b_press`;
- `clean_pause_resume`.

The exact Xbox Store 1.5.6 source profile contains no `actionPass` filters, but the builder preserves the rule for compatible variants.

## Whole-file compatibility

KCD2 uses last-mod-wins for `defaultProfile.xml`. The release is therefore explicitly version-specific.

The repository versions the reviewed Xbox 1.5.6 patched profile as release source. Development builders can regenerate it from an exact installation profile and fail closed when expected retail routes differ.

Another mod that replaces `defaultProfile.xml` conflicts with Clean Pause unless the files are deliberately merged.

## Forbidden paths

- `ActionMapManager.InitActionMaps()` — previously destroyed controller/action-map state globally;
- runtime supplemental Start map via `LoadFromXML()` — failed twice on the target build;
- runtime `EnableActionFilter()` — absent from the target retail Lua surface;
- `Player.OnAction` replacement;
- native input hook unless the official path is proven insufficient;
- `Menu.gfx` replacement;
- external overlay/OCR.

## Remaining runtime gates

The next prerelease must prove:

- exact `consoleCMD` press routing works for Escape and Xbox Start;
- successful entry consumes the same button release;
- failed custom entry would leave vanilla release fallback usable;
- zero visible vanilla pause-menu frame on successful entry;
- subtitle persistence under `Game.PauseGame(true)`;
- input isolation from the exclusive overlay-priority map;
- B resume without dialogue/cutscene side effects;
- real vanilla-menu handoff through `MenuEvents`;
- coherent audio/cutscene pause and resume.
