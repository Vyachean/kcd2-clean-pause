# KCD2 Clean Pause

Clean Pause is a small **Kingdom Come: Deliverance II** mod whose goal is to pause the game without covering the current rendered frame.

Target UX with an Xbox controller:

```text
Running
  Menu / Start -> Clean Pause

Clean Pause
  B            -> Resume
  Menu / Start -> vanilla KCD2 pause menu
```

The first Start press must not show the vanilla pause overlay, even for one frame. The main product use case is being able to leave the current subtitle visible for as long as needed.

## Target

Primary acceptance target:

- KCD2 **1.5.6**;
- PC Xbox Store / Xbox app / Game Pass;
- Xbox controller.

## Current status

**Retail test candidate; not a stable release yet.**

The current implementation uses only KCD2's normal `.pak`/Lua mod path. It does **not** require `version.dll`, ASI, KCSE, an external process, or an overlay.

KCD2 uses last-mod-wins for `defaultProfile.xml`, so this implementation is intentionally version-specific. The repository contains the patched Xbox 1.5.6 profile as target-specific release source and GitHub Actions packages it into the installable mod. No user's game file or GitHub Actions secret is required to reproduce a release.

The original Xbox Store 1.5.6 profile used to prepare that target source is documented in [docs/RETAIL_TEST1.md](docs/RETAIL_TEST1.md).

## Downloads

**GitHub Releases are the canonical distribution channel.** Generated `.pak`/`.zip` files are not committed to the repository.

The normal release flow is:

```text
PR / source commit
  -> CI validation
  -> version tag (for example v0.1.0-rc.1)
  -> GitHub Actions build
  -> GitHub Release + ZIP + SHA256SUMS.txt
```

`.github/workflows/release.yml` is triggered by `v*` tags and builds only from files contained in that tagged commit. See [docs/RELEASE.md](docs/RELEASE.md).

## Architecture

KCD2 1.5.6 uses two different semantic Start actions:

```text
ordinary gameplay        open_menu/open_menu

dialogue/cutscene/etc.   open_pause_menu/open_pause_menu
```

Both are already bound to `xi_start` in the retail profile. The patched release profile keeps their action IDs and physical bindings intact, but turns each action into a single-fire `consoleCmd` routed to Clean Pause.

First Start:

```text
retail open_menu/open_pause_menu
  -> CleanPause.Enter()
  -> enable clean_pause_controls
  -> Game.PauseGame(true)
  -> CleanPaused
```

`clean_pause_controls` is defined in the patched retail profile as:

```text
priority="overlays"
exclusivity="1"
```

It is disabled outside Clean Pause. While active it owns:

- Start press -> `clean_pause_open_menu`;
- B press -> sink action so a dialogue/cutscene press cannot escape;
- B release -> `clean_pause_resume`.

B resumes with `Game.PauseGame(false)`. Second Start does **not** unpause first; it disables the temporary controls map and calls the real KCD2/CryEngine UI event bridge:

```lua
UIAction.CallFunction("MenuEvents", -1, "DisplayIngameMenu", true)
```

The vanilla menu then owns its normal pause/input lifecycle.

Relevant retail `actionPass` filters that already allow a vanilla pause action are extended with the three temporary Clean Pause actions. Existing `actionFail` restrictions are left untouched.

## Release source

The target-specific patched profile used by releases is stored at:

```text
vendor/kcd2/xbox-1.5.6/defaultProfile.clean-pause.xml.gz
```

Its decompressed SHA-256 is:

```text
28e210454d749869b1fa26d4414ba3c055157e731856f9610d6ffce5ddfbc373
```

`tools/build_release.py` verifies this digest and builds the same package that the tag workflow publishes.

## Safety constraints

The implementation intentionally does **not**:

- call `ActionMapManager.InitActionMaps()`;
- call runtime `ActionMapManager.LoadFromXML()`;
- call the retail-unavailable `ActionMapManager.EnableActionFilter()`;
- replace `Player.OnAction`;
- remap the controller persistently;
- replace `Menu.gfx`;
- install native DLL/ASI code.

A previous experiment using `InitActionMaps()` disabled controller input globally. That API is permanently forbidden here.

## Development builders

The repository also keeps fail-closed tools for preparing/checking another exact game profile during development.

### From the installed game PAK

```powershell
python tools/build_from_game.py "C:\XboxGames\Kingdom Come- Deliverance II\Content"
```

### From an already extracted `defaultProfile.xml`

```powershell
python tools/build_from_profile.py "C:\path\to\defaultProfile.xml"
```

These are maintainer/development paths. Public downloads are produced by `tools/build_release.py` from the tagged repository source.

## Installation

Download the candidate ZIP from GitHub Releases. Extract its `clean_pause` directory into:

```text
%USERPROFILE%\Documents\kingdomcome_mods\
```

so the final path is:

```text
%USERPROFILE%\Documents\kingdomcome_mods\clean_pause\mod.manifest
```

Do not install this `.pak` beside `KingdomCome.exe`.

## Compatibility

Because the official mod path requires overriding the complete `defaultProfile.xml`, this build conflicts with another mod that also supplies that file. Do not test Clean Pause together with another keybind/profile mod until their changes are merged intentionally.

The release target is explicitly KCD2 1.5.6. A future game update requires a new reviewed target profile and a new release.

## What retail testing still has to prove

Static validation cannot prove these engine behaviours:

1. `Game.PauseGame(true)` keeps the current subtitle/frame visible;
2. the overlay-priority exclusive controls map suppresses lower gameplay/dialogue/cutscene input exactly as expected on retail 1.5.6;
3. `MenuEvents.DisplayIngameMenu(true)` is exposed under the inherited CryEngine event-system name;
4. dialogue/cutscene audio and progression resume coherently.

See [docs/TESTING.md](docs/TESTING.md) for the exact test sequence.

## Documentation

- [docs/DESIGN.md](docs/DESIGN.md) — current state machine and official-only architecture;
- [docs/RESEARCH.md](docs/RESEARCH.md) — confirmed retail/API findings and remaining hypotheses;
- [docs/TESTING.md](docs/TESTING.md) — Xbox Store 1.5.6 acceptance procedure;
- [docs/RETAIL_TEST1.md](docs/RETAIL_TEST1.md) — provenance of the first real Xbox retail test candidate;
- [docs/RELEASE.md](docs/RELEASE.md) — tag-based CI / GitHub Release pipeline;
- [docs/PURE_PROFILE_PLAN.md](docs/PURE_PROFILE_PLAN.md) — implementation-stage status;
- [docs/PURE_MOD_REFERENCES.md](docs/PURE_MOD_REFERENCES.md) — source/reference evidence.
