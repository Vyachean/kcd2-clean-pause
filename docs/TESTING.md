# rc.5 native diagnostic — Xbox Store / Game Pass 1.5.6

## Superseded / failed prereleases

- `v0.1.0-rc.1` — Escape/Start broken;
- `v0.1.0-rc.2` — Escape/Start still broken;
- `v0.1.0-rc.3` — safe F10 profile diagnostic; proved Lua command routing works but tested only unavailable `Game.PauseGame`;
- `v0.1.0-rc.4` — native ABI failure: Escape/Start made input unresponsive while gameplay continued. Root cause: gEnv `+0x98` is `IGame*`, not `IGameFramework*`; slot 13 was `IGame::GetName()`, not PauseGame.

`rc.5` is intentionally a **safe diagnostic**, not the final Start/Menu behavior.

## Install isolation

1. Close KCD2.
2. Delete/disable the old profile mod if present:

```text
%USERPROFILE%\Documents\kingdomcome_mods\clean_pause
```

3. Extract the `rc.5` native prerelease ZIP.
4. Replace the previous Clean Pause `version.dll` beside `KingdomCome.exe` / `WHGame.dll` with the `rc.5` file.
5. Start KCD2 normally.

Do **not** overwrite an unrelated mod's `version.dll`. Do **not** take ownership of `WindowsApps` or weaken Windows permissions just for this test.

The diagnostic writes:

```text
kcd2_clean_pause_native.log
```

beside `version.dll`.

## 1. Bootstrap / vanilla-input safety

At the title menu:

- Xbox controller navigation must remain normal;
- keyboard/mouse must remain normal;
- no unexpected pause or input loss.

Load a save and verify:

- **Escape opens the normal KCD2 pause menu**;
- **Xbox Start/Menu opens the normal KCD2 pause menu**.

This is a hard rc.5 contract. The hook contains no Start/Escape special case; only F10 is reserved. If Escape/Start are not vanilla, stop and attach the native log.

Expected bootstrap log contains a line beginning:

```text
rc5 diagnostic hook active;
```

and identifies `game(IGame*)=...` rather than `framework=...`.

## 2. F10 pause primitive probe

Return to normal gameplay with no vanilla menu open, then press **F10 once**.

Desired diagnostic result:

- gameplay/world freezes;
- dialogue/cutscene progression freezes if tested there;
- no vanilla pause overlay appears;
- the current rendered frame remains visible.

Regardless of whether the pause succeeds, **other controls must not become permanently unresponsive**. rc.5 has no global input-swallow state.

The important log line is:

```text
Lua pause probe paused=true available=<true|false> route=<CryAction.PauseGame|Action.PauseGame|Game.PauseGame|none> pcall=<true|false>
```

The probe tries bindings in this order:

1. `CryAction.PauseGame(true)`;
2. `Action.PauseGame(true)`;
3. `Game.PauseGame(true)`.

## 3. F10 resume probe

If the first F10 actually paused the game, press **F10 again**.

Expected:

- gameplay resumes;
- log contains the same route with:

```text
Lua pause probe paused=false ... pcall=true
F10 probe: requested resume through retail Lua pause binding
```

## 4. Minimal dialogue/subtitle probe

Only if F10 pause/resume works in exploration:

1. enter dialogue with a visible subtitle;
2. press F10 during the line;
3. wait longer than the subtitle would normally remain;
4. note whether the exact subtitle stays visible and speech/progression stop;
5. press F10 again to resume.

This establishes whether the retail pause primitive satisfies the actual Clean Pause goal before Start/Menu interception is reintroduced.

## Evidence to report

Report the visible results for:

- Escape;
- Start/Menu;
- first F10;
- second F10 if the first paused.

Also attach `kcd2_clean_pause_native.log`, especially the `Lua pause probe ...` lines.

Do not test B/second-Start Clean Pause semantics in rc.5; they are deliberately disabled until the pause primitive is proven.
