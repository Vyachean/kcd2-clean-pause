# KCD2 Clean Pause

Experimental **Kingdom Come: Deliverance II** mod targeting the eventual interaction:

```text
Running
  Xbox Menu / Start -> Clean Pause

Clean Pause
  B                  -> Resume
  Xbox Menu / Start  -> vanilla KCD2 pause menu
```

The goal is to freeze gameplay, dialogue and in-engine cutscenes without covering the current rendered frame, so a visible subtitle can remain on screen.

## Target

- KCD2 **1.5.6**
- PC Xbox Store / Xbox app / Game Pass
- Xbox controller; Escape is intended to behave analogously

## Retail findings

`v0.1.0-rc.1` and `rc.2` broke normal Escape/Start pause routing and are obsolete.

`v0.1.0-rc.3` was an intentionally safe profile/Lua diagnostic. Retail testing proved that the PAK, Lua bootstrap, `System.AddCCommand`, `consoleCMD`, and F10 routing all work. Its pause attempt failed specifically because it tested `Game.PauseGame`, which is unavailable in the tested Xbox Store 1.5.6 runtime.

`v0.1.0-rc.4` moved pause acquisition to a native `version.dll`, but retail testing exposed a more serious ABI error: pressing Escape/Start left the game running while input became unresponsive.

The rc.4 root cause is now identified:

- KCD2 1.5.6 `SSystemGlobalEnvironment + 0x98` is verified as **`IGame*`**, not `IGameFramework*`;
- `IGame` slot 13 is `GetName()` and returns `"kcd2"`;
- rc.4 called that slot through a PauseGame-shaped function pointer;
- because the wrong call did not raise an access violation, rc.4 incorrectly set its own `g_cleanPaused` flag and started consuming input although the simulation had never paused.

That direct native pause ABI is permanently rejected by CI.

## Current diagnostic implementation

The next prerelease (`rc.5`) is deliberately **not** a Start/Menu Clean Pause candidate. It exists to prove the actual retail pause primitive safely.

The native diagnostic build:

- loads as a `version.dll` proxy;
- hooks KCD2's raw `IInput::PostInputEvent` only to reserve **F10**;
- leaves **Escape and Xbox Start completely untouched/vanilla**;
- corrects `gEnv + 0x98` to `IGame*` and uses it only as a structural runtime anchor;
- never calls an inferred `IGameFramework` pause vfunc;
- never enters a persistent input-swallow state;
- on F10 probes the documented/observed Lua bindings in this order:
  1. `CryAction.PauseGame(bool)`;
  2. `Action.PauseGame(bool)`;
  3. legacy `Game.PauseGame(bool)`;
- logs the selected route and Lua `pcall` result;
- a second F10 requests resume if the first probe call completed successfully.

Warhorse ScriptBind documentation defines `Action.PauseGame(pause)` as putting the game into or out of pause mode. A captured KCD2 Lua global-state dump also exposes `PauseGame()` under `CryAction`. rc.3 simply never tested those two bindings.

See [docs/RC5_DIAGNOSTIC.md](docs/RC5_DIAGNOSTIC.md) for the failure analysis and acceptance gate.

## Safety constraints

Permanent rules:

- never call `ActionMapManager.InitActionMaps()`;
- never reload a partial action-map profile at runtime;
- never persistently remap the controller;
- never replace `Player.OnAction`;
- never treat "native call did not crash" as proof that pause succeeded;
- fail open to vanilla input whenever a runtime assumption cannot be verified.

An earlier `InitActionMaps()` prototype disabled Xbox-controller input globally, including the title menu; that API is permanently forbidden.

## Distribution

GitHub Releases are the canonical channel. Generated DLL/ZIP files are not committed.

```text
implementation PR
  -> Validate CI + Release build/package CI
  -> merge to main
  -> release PR changes VERSION
  -> CI
  -> merge to main
  -> GitHub Actions builds version.dll
  -> Linux job verifies the exact artifact
  -> GitHub Release + ZIP + SHA256SUMS.txt
```

For native candidates, remove the old `Documents\kingdomcome_mods\clean_pause` PAK before testing so only one implementation is active.

See:

- [docs/RC5_DIAGNOSTIC.md](docs/RC5_DIAGNOSTIC.md)
- [docs/RESEARCH.md](docs/RESEARCH.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/RELEASE.md](docs/RELEASE.md)
