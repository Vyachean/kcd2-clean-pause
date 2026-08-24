# Research notes

This file separates confirmed KCD2 facts from behaviours that still require retail testing.

## Confirmed retail 1.5.6 pause routes

The exact Xbox Store 1.5.6 `defaultProfile.xml` contains two semantic pause routes:

```text
ordinary gameplay        open_menu/open_menu
dialogue/cutscene/etc.   open_pause_menu/open_pause_menu
```

Both original actions have:

```text
onPress="1"
onRelease="1"
keyboard="_keybinds_ref_"
xboxpad="xi_start"
pspad="pad_start"
```

The profile override is definitely loaded by the mod package: both rc1 and rc2 changed the observed behaviour of Escape/Start on the target retail build.

## Confirmed: `consoleCMD`

KCD2 keybind/superaction examples use the exact attribute:

```xml
consoleCMD="1"
```

`v0.1.0-rc.1` incorrectly used `consoleCmd="1"`. XML attribute names are case-sensitive.

What is **not yet confirmed** is whether our packed `Scripts/Mods/clean_pause.lua` executes and whether a custom `consoleCMD` profile action successfully reaches a command registered through `System.AddCCommand` on the Xbox Store build.

That is the purpose of the F10 diagnostic candidate.

## Confirmed failure: `v0.1.0-rc.1`

Observed on Xbox Store 1.5.6:

- Escape did nothing;
- Xbox Start did nothing;
- Clean Pause did not activate.

Problems:

- wrong-case `consoleCmd`;
- original vanilla pause actions had been replaced outright.

## Confirmed failure: `v0.1.0-rc.2`

Observed on the same target:

- Escape still did nothing;
- Xbox Start still did nothing.

rc2 used exact `consoleCMD`, but changed the original vanilla actions to `onRelease`-only and added separate custom press actions.

This disproves the assumption that an `onRelease`-only original action provides a usable independent vanilla fallback in KCD2. Presence of the XML route in the profile is not enough; the actual retail dispatch semantics do not give us the fallback behaviour we expected.

Permanent consequence: **do not modify Start/Escape again until the Lua/console-command layer is independently proven.**

## Diagnostic design after rc2

The next candidate is derived from the already integrity-checked rc2 source at build time.

It restores both vanilla actions to:

```text
onPress="1" + onRelease="1"
_keybinds_ref_
xi_start
non-console
```

The rc2 custom entry slots are converted into keyboard-only probes:

```text
clean_pause_probe_gameplay       -> F10, consoleCMD="1"
clean_pause_probe_pause_context  -> F10, consoleCMD="1"
```

The probes have no controller bindings. Filter references that previously pointed to the rc2 custom entry actions are renamed to the corresponding F10 probe names.

This isolates the runtime chain:

```text
F10 profile action
  -> consoleCMD
  -> System.AddCCommand registration
  -> Scripts/Mods/clean_pause.lua
  -> CleanPause.Enter()
  -> Game.PauseGame(true)
```

Possible retail outcomes:

- vanilla Esc/Start work + F10 works -> Lua/bootstrap/console route proven; only Start interception remains;
- vanilla Esc/Start work + F10 does nothing + no `[Clean Pause]` bootstrap log -> investigate Lua bootstrap/package loading;
- vanilla Esc/Start work + bootstrap log exists + F10 does nothing -> investigate command registration/action routing;
- vanilla Esc/Start do not work -> diagnostic package violated its safety contract and must not be used further.

## Confirmed APIs / constraints

Warhorse/KCD2 documentation exposes:

```lua
System.AddCCommand(...)
Game.PauseGame(true)
Game.PauseGame(false)
ActionMapManager.EnableActionMap(...)
ActionMapManager.IsFilterEnabled(...)
UIAction.CallFunction(...)
```

The retail ActionMapManager surface does **not** expose `EnableActionFilter`.

`ActionMapManager.InitActionMaps()` is permanently forbidden: an earlier retail prototype using it broke Xbox-controller input globally, including the initial menu.

A supplemental runtime Start map through `LoadFromXML()` also failed twice: the custom Start action never fired while vanilla Start remained functional.

## Remaining product questions

Only after the F10 probe succeeds should the project return to these questions:

1. how to intercept Xbox Start without breaking the vanilla route;
2. whether first Clean Pause has zero menu flash;
3. whether `Game.PauseGame(true)` keeps the current subtitle visible indefinitely;
4. whether `clean_pause_controls` isolates lower gameplay/dialogue/cutscene input;
5. whether B resumes without skip/cancel side effects;
6. whether `MenuEvents.DisplayIngameMenu(true)` opens the real vanilla pause menu on the second Start;
7. whether audio/camera/animation/scripted progression pause and resume coherently.

Do not infer answers to these from static CI; they require retail observation.
