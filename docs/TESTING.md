# Retail testing — Xbox Store / Game Pass 1.5.6

This branch is a **test candidate**, not a release. Test only a ZIP generated from the same installed KCD2 copy that will run it.

## 1. Build from the installed game

Close KCD2 first.

From branch `prototype/pure-profile`:

```powershell
python tools/build_from_game.py "C:\XboxGames\Kingdom Come- Deliverance II\Content"
```

Expected output includes:

```text
Profile version: 0
Routed Start actions: open_menu/open_menu, open_pause_menu/open_pause_menu
Built: ...\release\kcd2-clean-pause-xbox-1.5.6-test.zip
```

If the builder refuses the profile, stop. Do not bypass the check or substitute another `defaultProfile.xml`.

## 2. Install

For Xbox Store / Game Pass, extract the generated `clean_pause` directory to:

```text
%USERPROFILE%\Documents\kingdomcome_mods\
```

Expected final structure:

```text
Documents\kingdomcome_mods\clean_pause\
  mod.manifest
  Data\clean_pause.pak
```

Do not install this PAK in the executable directory. For this first test, disable any other mod that replaces `Libs/Config/defaultProfile.xml`.

## 3. Controller safety gate

1. Launch KCD2 with the Xbox controller connected.
2. Verify normal controller navigation in the title/front-end menu.
3. Load a save.
4. Verify movement, camera, A/B/X/Y, triggers, shoulders, sticks, D-pad, View and Menu behave normally.

If unrelated controller input is broken, stop testing and remove the mod.

## 4. Ordinary gameplay — first Start

In normal exploration, press Menu / Start once.

Expected:

- the world freezes;
- camera/frame stays fixed;
- **no vanilla pause overlay or dark frame appears at all**;
- HUD remains as rendered;
- normal gameplay controls do not move/act while clean-paused.

Search `kcd.log` for:

```text
[Clean Pause] official runtime loaded; routed actions=open_menu,open_pause_menu
[Clean Pause] entered clean pause from open_menu
```

Failure interpretation:

- vanilla menu opens immediately -> the effective `open_menu` route was not replaced;
- Start does nothing -> inspect `[Clean Pause]` registration/runtime lines and profile-mod load order;
- game pauses but unrelated inputs still act -> exclusive-map isolation failed and must be fixed before release.

## 5. B resume

While clean-paused, press and release B once.

Expected:

```text
[Clean Pause] resumed
```

and gameplay resumes normally.

In dialogue/cutscene testing, the B press/release must **not** skip/cancel anything. B resume is deliberately triggered on release and the temporary map contains a B-press sink.

## 6. Second Start -> vanilla pause menu

Enter Clean Pause again, then press Menu / Start.

Expected:

- the real vanilla KCD2 pause menu opens;
- there is no intermediate gameplay unpause;
- log contains `[Clean Pause] handed pause ownership to vanilla menu`.

Close the vanilla menu normally with B. The game must return to ordinary running gameplay and Clean Pause must not reactivate automatically.

If second Start does nothing, look for `MenuEvents.DisplayIngameMenu(true) unavailable` or another `MenuEvents` error.

## 7. Subtitle acceptance test

1. Start a normal dialogue with subtitles visible.
2. Wait for a clearly readable subtitle line.
3. Press Start.
4. Leave Clean Pause active longer than the line would normally remain.
5. Confirm the **same subtitle remains visible**.
6. Confirm speech/progression has stopped.
7. Press/release B.
8. Confirm dialogue resumes from the same point without skip, duplicate line or desync.

Repeat in at least one in-engine cutscene.

## 8. Input isolation test

While Clean Pause is active, deliberately try A, X, Y, D-pad, shoulders/triggers, both sticks and View/Back before using B/Start.

Expected: no gameplay/dialogue/cutscene action and no camera movement occurs.

This validates `priority="overlays" exclusivity="1"` on retail KCD2 1.5.6.

## 9. Scenario matrix

| Scenario | Start enters clean pause | zero overlay | frame fixed | subtitle retained | B resumes without side effect | second Start opens vanilla menu |
| --- | --- | --- | --- | --- | --- | --- |
| Exploration | required | required | required | n/a | required | required |
| Combat | required | required | required | if present | required | required |
| Dialogue | required | required | required | **required** | **required** | required |
| In-engine cutscene | required | required | required | **required** | **required** | required |
| Mounted gameplay | required | required | required | if present | required | required |

Prerendered video is a separate capability test and may be engine-limited.

## 10. Robustness

After the core matrix passes, check repeated pause/resume cycles, pause near subtitle/cutscene transitions, clean pause -> vanilla menu, loading a save from that menu, death/game-over, controller reconnect, Alt-Tab, and return to main menu.

No case may leave the game unexpectedly paused or leave `clean_pause_controls` active after Clean Pause relinquishes ownership.

## Uninstall

Close the game and delete:

```text
%USERPROFILE%\Documents\kingdomcome_mods\clean_pause
```

No controller/profile repair should be necessary.

## Release gate

Do not call this released until all are true:

- title/front-end controller behaviour is unchanged;
- first Start shows zero pause-menu frame;
- normal gameplay/dialogue/in-engine cutscene all enter Clean Pause;
- subtitle remains visible while paused;
- audio/progression pauses coherently;
- unrelated input is isolated while paused;
- B resumes without triggering the underlying context action;
- second Start opens the untouched vanilla pause menu;
- vanilla menu closes normally;
- repeated transitions leave no stuck pause/input state.
