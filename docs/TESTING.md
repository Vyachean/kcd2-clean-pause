# Hidden vanilla pause candidate — Xbox Store / Game Pass 1.5.6

## Superseded / failed prereleases

- `v0.1.0-rc.1` — Escape/Start broken;
- `v0.1.0-rc.2` — Escape/Start still broken;
- `v0.1.0-rc.3` — safe F10 profile diagnostic; proved Lua command routing works but tested only unavailable `Game.PauseGame`;
- `v0.1.0-rc.4` — native ABI failure: Escape/Start made input unresponsive while gameplay continued. Root cause: gEnv `+0x98` is `IGame*`, not `IGameFramework*`; slot 13 was `IGame::GetName()`, not PauseGame;
- `v0.1.0-rc.5` — safe Lua-pause diagnostic. Retail test proved the pause binding freezes world simulation, but audio/UI continue and subtitles expire. It is therefore a partial simulation freeze, not the full pause lifecycle required by Clean Pause.

## Current architecture under test

The candidate does **not** call any custom pause primitive.

On first Escape/Xbox Start:

1. check that a player exists and `only_ui` is not already active;
2. forward the physical event to KCD2 unchanged;
3. verify that vanilla KCD2 enabled `only_ui`;
4. hide only the retail `Menu@0` Flash element.

This keeps the actual pause/audio/dialog/cutscene state entirely vanilla.

## Install isolation

1. Close KCD2.
2. Delete/disable the old profile mod if present:

```text
%USERPROFILE%\Documents\kingdomcome_mods\clean_pause
```

3. Extract the native prerelease ZIP.
4. Replace the previous Clean Pause `version.dll` beside `KingdomCome.exe` / `WHGame.dll`.
5. Start KCD2 normally.

Do **not** overwrite an unrelated mod's `version.dll`. Do **not** take ownership of `WindowsApps` or weaken Windows permissions just for this test.

The build writes:

```text
kcd2_clean_pause_native.log
```

beside `version.dll`.

## 1. Bootstrap / vanilla-input safety

At the title menu:

- Xbox controller navigation remains normal;
- keyboard/mouse remain normal;
- no unexpected pause/input loss.

Load a save. Before testing the mod behavior, ordinary gameplay controls must be normal.

Expected bootstrap log begins with:

```text
hidden-vanilla-pause hook active;
```

## 2. First Escape / Start — Clean Pause

In normal exploration press **Escape** or **Xbox Start/Menu** once.

Expected:

- world/simulation stops;
- audio follows the normal KCD2 pause behavior rather than continuing as in rc.5;
- no visible pause-menu UI covers the frame;
- controls other than the defined Clean Pause controls do nothing;
- log contains:

```text
Running -> Clean Pause: vanilla pause retained, Menu@0 hidden (...)
```

Hard failure conditions:

- gameplay continues while input becomes unresponsive;
- ordinary visible pause menu appears and remains despite a successful hide log;
- game crashes;
- sound/UI continue exactly like the rc.5 partial freeze.

If vanilla pause opens visibly instead, this is a safe fail-open; keep the log because it should explain whether `only_ui` verification or Menu hiding failed.

## 3. B resume

While Clean Paused press **Xbox B**.

Expected:

- vanilla pause closes;
- gameplay/audio resume;
- B does not leak into gameplay/dialogue/cutscene;
- no visible pause-menu frame flashes;
- log contains:

```text
Clean Pause -> running via vanilla B/back
```

## 4. Second Escape / Start

Enter Clean Pause again, then press **Escape/Start** a second time.

Expected:

- the already-open normal KCD2 pause menu becomes visible;
- gameplay remains paused continuously;
- there is no intermediate simulation/audio tick;
- the second physical Escape/Start is consumed rather than closing the menu;
- log contains:

```text
Clean Pause -> visible vanilla pause menu (second Escape/Start consumed)
```

Close the visible vanilla menu normally and confirm gameplay returns to normal.

## 5. Dialogue/subtitle acceptance test

1. Enter dialogue with a visible subtitle.
2. Press Escape/Start during the spoken line.
3. Wait longer than the subtitle would normally remain.
4. Check separately:
   - speech remains paused;
   - dialogue progression remains paused;
   - the **same subtitle remains visible**;
   - no new UI hint/state appears because of hidden-menu navigation.
5. Press B and confirm the dialogue resumes without skip/cancel/duplicate.

Subtitle retention is a key acceptance gate. A full vanilla pause may still hide HUD/subtitle presentation even when `Menu@0` is hidden; if that happens, report it exactly rather than treating the pause itself as failed.

## 6. In-engine cutscene

Repeat the first-pause / wait / B-resume sequence in an in-engine cutscene if practical.

Expected:

- cutscene progression and audio pause together;
- no skip/cancel action leaks;
- B resumes rather than skipping.

## 7. Robustness

Repeat several times across:

- exploration;
- dialogue;
- in-engine cutscene;
- after loading a save;
- Alt-Tab / return;
- controller reconnect if convenient.

At no point should a failed runtime assumption leave gameplay running with input swallowed. Failure must degrade to ordinary vanilla input/pause behavior.

## Evidence to report

Report visible behavior for:

- first Escape;
- first Start/Menu;
- B resume;
- second Escape/Start;
- dialogue subtitle retention;
- audio behavior.

Attach `kcd2_clean_pause_native.log` if any result differs from the expectations above.
