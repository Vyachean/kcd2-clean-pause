# Retail diagnostic test — Xbox Store / Game Pass 1.5.6

## Known failed prereleases

Do not use these for further acceptance testing:

- `v0.1.0-rc.1` — Escape and Xbox Start did nothing;
- `v0.1.0-rc.2` — Escape and Xbox Start still did nothing.

`rc.2` disproved the assumption that the original pause action remains a usable vanilla fallback after being changed to `onRelease`-only.

## Purpose of the next candidate

The next prerelease is a **diagnostic probe**, not another Start-interception attempt.

The release builder restores the original retail pause actions to:

```text
onPress="1"
onRelease="1"
keyboard="_keybinds_ref_"
xboxpad="xi_start"
```

They remain non-console actions. A separate keyboard-only **F10** action tests:

```text
consoleCMD="1"
  -> System.AddCCommand
  -> Scripts/Mods/clean_pause.lua
  -> CleanPause.Enter()
  -> Game.PauseGame(true)
```

The F10 probe has no controller binding.

## 1. Install

Close KCD2 and delete the previous mod directory completely:

```text
%USERPROFILE%\Documents\kingdomcome_mods\clean_pause
```

Extract the new release so this exists:

```text
%USERPROFILE%\Documents\kingdomcome_mods\clean_pause\mod.manifest
```

Disable any other mod that replaces `Libs/Config/defaultProfile.xml`.

## 2. Verify vanilla pause first

Load an ordinary exploration save.

1. Press **Escape**. The normal KCD2 pause menu must open.
2. Close it.
3. Press **Xbox Start/Menu**. The normal KCD2 pause menu must open.

If either control does nothing, stop testing and report it. The diagnostic package is specifically built to leave these routes vanilla.

## 3. F10 probe

Return to ordinary running exploration and press **F10** once.

### A. F10 clean-pauses

Expected:

- world/game progression freezes;
- no vanilla pause overlay appears;
- current rendered frame remains visible.

`kcd.log` should contain lines similar to:

```text
[Clean Pause] official runtime loaded; routed actions=clean_pause_probe_gameplay,clean_pause_probe_pause_context
[Clean Pause] entered clean pause from clean_pause_probe_gameplay
```

Press and release **B** once. Expected:

```text
[Clean Pause] resumed
```

Report that F10 worked. This proves the Lua/bootstrap + `System.AddCCommand` + `consoleCMD` + `Game.PauseGame(true)` chain. Do not proceed to the full subtitle/cutscene matrix yet.

### B. F10 does nothing

Close the game and check `kcd.log` for `[Clean Pause]`.

The important distinction is:

```text
no [Clean Pause] lines at all
```

versus a bootstrap line such as:

```text
[Clean Pause] official runtime loaded; ...
```

- no bootstrap line -> investigate mod Lua loading/bootstrap;
- bootstrap exists but F10 is inert -> investigate command registration / `consoleCMD` action routing.

Do not modify Start bindings again until this layer is understood.

## CI contract

PR/release CI opens the final generated PAK and requires:

- `open_menu/open_menu` has both `onPress="1"` and `onRelease="1"`;
- `open_pause_menu/open_pause_menu` has both `onPress="1"` and `onRelease="1"`;
- both retain `_keybinds_ref_` and `xi_start`;
- neither vanilla action is a console command;
- the diagnostic actions use `keyboard="f10"` and exact `consoleCMD="1"`;
- the diagnostic actions have no Xbox/PlayStation binding;
- generated Lua registers the diagnostic action names;
- `ActionMapManager.InitActionMaps()` remains forbidden.

## After the probe

Only after F10 succeeds will Start interception be redesigned. Full subtitle persistence, dialogue/cutscene behavior, input isolation, B resume and second-Start menu handoff remain later acceptance gates.
