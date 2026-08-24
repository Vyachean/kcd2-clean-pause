# Native retail test — Xbox Store / Game Pass 1.5.6

## Superseded prereleases

- `v0.1.0-rc.1` — Escape/Start broken;
- `v0.1.0-rc.2` — Escape/Start still broken;
- `v0.1.0-rc.3` — safe F10 diagnostic; proved Lua command routing works but retail reports `Game.PauseGame unavailable`.

Do not install the old PAK together with the native candidate.

## Install isolation

1. Close KCD2.
2. Delete/disable:

```text
%USERPROFILE%\Documents\kingdomcome_mods\clean_pause
```

3. Extract the native prerelease ZIP.
4. Put its `version.dll` in the same directory as `KingdomCome.exe` / `WHGame.dll`.
5. Start KCD2 normally.

Do **not** take ownership of `WindowsApps` or weaken Windows permissions just to install this test. If the storefront installation does not permit placing the DLL beside the executable, report that as an installation result.

The native loader writes:

```text
kcd2_clean_pause_native.log
```

beside `version.dll`.

## 1. Bootstrap safety

At the title menu:

- Xbox controller navigation must remain normal;
- keyboard/mouse must remain normal;
- no unexpected pause or input loss.

If controller input is globally broken, remove `version.dll` and stop.

Expected native log after successful initialization includes a line beginning:

```text
native hook active;
```

If the hook cannot validate KCD2 1.5.6 runtime/slot 13, it must not install; vanilla input should remain functional.

## 2. First Clean Pause

Load a normal exploration save and press **Xbox Start/Menu**.

Expected:

- gameplay freezes immediately;
- vanilla pause menu does not appear, even for one frame;
- current rendered frame/HUD stays visible;
- native log contains:

```text
IGameFramework::PauseGame(true, true, 0) invoked
Running -> Clean Pause (pause input consumed before ActionMapManager)
```

Repeat with **Escape**.

If Start/Escape opens vanilla pause instead, attach the native log: fail-open probably occurred before or during pause acquisition.

## 3. Input isolation

While Clean Paused try:

- A/X/Y;
- D-pad;
- shoulders/triggers;
- sticks;
- View/Back;
- mouse/keyboard gameplay inputs.

Expected: no gameplay/dialogue/camera action. Clean Pause consumes underlying input while it owns pause state.

## 4. B resume

While Clean Paused press B once.

Expected:

- gameplay resumes;
- B does not cause an underlying gameplay/dialogue action;
- log contains:

```text
IGameFramework::PauseGame(false, true, 0) invoked
Clean Pause -> Running (B consumed)
```

## 5. Second Start -> vanilla pause

Enter Clean Pause again, then press Start (or Escape).

Expected:

- the normal KCD2 pause menu opens;
- there is no intermediate gameplay/audio resume;
- log contains:

```text
Clean Pause -> vanilla pause menu (no intermediate unpause)
```

If the normal menu does not open, Clean Pause should remain active and the log should report that `MenuEvents.DisplayIngameMenu(true)` did not establish `only_ui`.

## 6. Subtitle/dialogue acceptance

1. Start dialogue with a visible subtitle.
2. Press Start during the line.
3. Wait longer than the subtitle would normally remain.
4. Confirm the **same subtitle stays visible**.
5. Confirm speech, animation/camera and scripted progression are stopped as expected.
6. Resume with B.
7. Confirm dialogue continues without skip/cancel/duplicate/desync.

Repeat during an in-engine cutscene.

## 7. Robustness

After core behavior works, test:

- repeated pause/resume;
- combat;
- mounted gameplay;
- dialogue/cutscene transitions;
- Clean Pause -> vanilla menu -> close menu;
- save/load from vanilla menu;
- death/game over;
- controller reconnect;
- Alt-Tab;
- return to main menu.

No path may leave the game stuck paused or leave input intercepted after Clean Pause relinquishes ownership.

## Evidence to report on failure

Attach `kcd2_clean_pause_native.log` and describe the visible result for:

- first Start;
- B while paused;
- second Start.

The old `kcd.log` F10 probe is no longer the primary diagnostic for native candidates.
