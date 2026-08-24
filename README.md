# KCD2 Clean Pause

Experimental **Kingdom Come: Deliverance II** mod targeting:

```text
Running
  Xbox Menu / Start -> Clean Pause

Clean Pause
  B                  -> Resume
  Xbox Menu / Start  -> vanilla KCD2 pause menu
```

The goal is to freeze gameplay, dialogue and in-engine cutscenes without covering the current rendered frame, so the visible subtitle can remain on screen.

## Target

- KCD2 **1.5.6**
- PC Xbox Store / Xbox app / Game Pass
- Xbox controller; Escape is supported too

## Retail findings

`v0.1.0-rc.1` and `rc.2` broke normal Escape/Start pause routing and are obsolete.

`v0.1.0-rc.3` was an intentionally safe diagnostic build: vanilla Escape/Start were restored and F10 independently tested the official-profile/Lua route. Retail testing proved all of the following:

- `clean_pause.pak` loads;
- `Scripts/Mods/clean_pause.lua` executes;
- `System.AddCCommand` registration works;
- the F10 `consoleCMD` action reaches `CleanPause.Enter()`;
- entry then fails with `[Clean Pause] Game.PauseGame unavailable`.

Independent retail closure data likewise contains no retail `PauseGame` Lua closure; `CryAction.PauseGame` is present only in KCDRewrite. Therefore another profile/Lua input experiment cannot provide the required true pause.

## Current implementation

Development has moved to the narrow native route in PR #10.

The native build:

- loads as a `version.dll` proxy;
- hooks KCD2's raw `IInput::PostInputEvent` before `ActionMapManager`;
- locates `SSystemGlobalEnvironment` at runtime rather than hard-coding a storefront RVA;
- validates `pGameFramework` and KCD2 1.5.6 vtable slot 13 before installing the hook;
- calls that slot directly as `IGameFramework::PauseGame(bool, true, 0)`;
- uses Lua only for read-only gameplay/UI eligibility and second-Start menu handoff;
- consumes unrelated game input only while Clean Pause owns pause state;
- forwards the original Escape/Start untouched if native initialization or pause acquisition fails.

The first pause press is consumed before KCD2's vanilla pause action, so the normal pause overlay should never receive that physical press.

While Clean Paused, B resumes through the same native pause primitive. Second Escape/Start asks the real `MenuEvents.DisplayIngameMenu(true)` to take UI ownership **without first unpausing**, avoiding the old prototype's possible one-tick gap.

## Safety constraints

Permanent rules:

- never call `ActionMapManager.InitActionMaps()`;
- never reload a partial action-map profile at runtime;
- never persistently remap the controller;
- never replace `Player.OnAction`;
- fail open to vanilla input if the pinned KCD2 1.5.6 ABI cannot be validated.

An earlier `InitActionMaps()` prototype disabled Xbox-controller input globally, including the title menu; that API is permanently forbidden.

## Distribution

GitHub Releases are the canonical channel. Generated DLL/ZIP files are not committed.

```text
implementation PR
  -> Validate CI (Linux source checks + Windows x64 native build)
  -> merge to main
  -> release PR changes VERSION
  -> Validate CI
  -> merge to main
  -> GitHub Actions builds version.dll and publishes ZIP + SHA256SUMS.txt
```

The next candidate will be a native prerelease; the old `Documents\kingdomcome_mods\clean_pause` PAK must be removed before testing it.

See:

- [docs/RESEARCH.md](docs/RESEARCH.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/RELEASE.md](docs/RELEASE.md)
