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
- Xbox controller;
- keyboard Escape is also covered by the pause route.

## Current status

**Retail prerelease development. `v0.1.0-rc.1` is known broken and must not be used.**

Retail testing of rc1 showed that neither Escape nor Xbox Start paused the game. The root cause was an incorrect XML action attribute (`consoleCmd` instead of KCD2's exact `consoleCMD`) combined with an unsafe design that had replaced the vanilla pause actions outright.

The current fix does two things:

1. uses exact KCD2 `consoleCMD="1"` actions;
2. retains vanilla pause as a release-time fallback so a Clean Pause command failure degrades to the normal KCD2 pause rather than removing pause entirely.

The implementation uses only KCD2's normal `.pak`/Lua mod path. It does **not** require `version.dll`, ASI, KCSE, an external process, or an overlay.

## Downloads

**GitHub Releases are the canonical distribution channel.** Generated `.pak`/`.zip` files are not committed to the repository.

Do not use `v0.1.0-rc.1`. The next retail candidate will be `v0.1.0-rc.2` after the fail-safe fix passes CI.

Release flow:

```text
implementation PR
  -> Validate CI
  -> merge to main
  -> release PR changes VERSION
  -> Validate CI
  -> merge to main
  -> GitHub Actions creates tag + GitHub Release
  -> ZIP + SHA256SUMS.txt
```

Direct matching `v*` tag publication is also supported by `.github/workflows/release.yml`.

## Pause routing

KCD2 1.5.6 uses two semantic pause actions:

```text
ordinary gameplay        open_menu/open_menu
dialogue/cutscene/etc.   open_pause_menu/open_pause_menu
```

Both retail actions use the normal keybind reference for keyboard and `xi_start` for Xbox Start.

The patched profile now splits each physical press/release cycle:

```text
Escape / Start press
  -> clean_pause_enter_gameplay
     or clean_pause_enter_pause_context
  -> consoleCMD
  -> CleanPause.Enter()
  -> enable clean_pause_controls
  -> Game.PauseGame(true)

Escape / Start release
  -> if Clean Pause succeeded:
       clean_pause_controls is exclusive
       clean_pause_block_start_release consumes release
  -> if Clean Pause failed to start:
       original open_menu/open_pause_menu release fires
       vanilla pause menu opens
```

The original `open_menu` and `open_pause_menu` actions therefore remain in the profile with their retail bindings, but are changed to **release-only** fallback actions. They are not console commands.

The custom press actions explicitly bind `keyboard="escape"` and `xboxpad="xi_start"`. The exact retail `no_menu` actionFail filter is mirrored to the custom gameplay entry, so Clean Pause cannot bypass a context in which vanilla pause is disabled.

## Clean-paused controls

`clean_pause_controls` is defined as:

```text
priority="overlays"
exclusivity="1"
```

It is disabled outside Clean Pause. While active it owns:

- Escape / Start press -> `clean_pause_open_menu`;
- Escape / Start release -> sink (`clean_pause_block_start_release`);
- B press -> sink;
- B release -> `clean_pause_resume`.

B resumes with `Game.PauseGame(false)`.

Second Start currently hands pause ownership to the vanilla UI through:

```lua
UIAction.CallFunction("MenuEvents", -1, "DisplayIngameMenu", true)
```

That path remains a retail acceptance item; the current fix is specifically designed so failure of the **first** Clean Pause entry can no longer remove normal pause functionality.

## Release source

KCD2 uses last-mod-wins for `defaultProfile.xml`, so this implementation is intentionally version-specific. The repository contains the patched Xbox 1.5.6 profile as deterministic gzip+base64 release source:

```text
vendor/kcd2/xbox-1.5.6/defaultProfile.clean-pause.xml.gz.b64
```

Original retail profile SHA-256:

```text
69ad9fd618cd31961fef8eb061f3f2723997df5e0fb257ec74d0d5f555592565
```

Current fail-safe patched profile SHA-256:

```text
9838db3747f7f36e0c9c281b8770bc7300998515407515b65493b8e9a9bcd14e
```

`tools/build_release.py` decodes it, verifies this digest and validates the complete fallback/console-command contract before packaging.

## Safety constraints

The implementation intentionally does **not**:

- call `ActionMapManager.InitActionMaps()`;
- call runtime `ActionMapManager.LoadFromXML()`;
- call the retail-unavailable `ActionMapManager.EnableActionFilter()`;
- replace `Player.OnAction`;
- remap the controller persistently;
- replace `Menu.gfx`;
- install native DLL/ASI code.

An earlier prototype using `InitActionMaps()` disabled controller input globally, including the title menu. That API is permanently forbidden here.

## Installation

Download the current candidate ZIP from GitHub Releases. Extract its `clean_pause` directory into:

```text
%USERPROFILE%\Documents\kingdomcome_mods\
```

Expected final path:

```text
%USERPROFILE%\Documents\kingdomcome_mods\clean_pause\mod.manifest
```

Do not install the PAK beside `KingdomCome.exe`.

For testing, disable any other mod that replaces `Libs/Config/defaultProfile.xml`.

## Compatibility

This build conflicts with another mod that supplies `defaultProfile.xml`. The release target is explicitly KCD2 1.5.6; another game version requires a newly reviewed target profile and release.

## Retail acceptance still required

The next candidate must prove:

1. Escape and Xbox Start execute Clean Pause on press;
2. if the custom entry cannot execute, vanilla pause remains available on release;
3. first pause has no vanilla menu flash;
4. `Game.PauseGame(true)` retains the current subtitle/frame;
5. unrelated input is isolated while paused;
6. B resumes without triggering dialogue/cutscene actions;
7. second Start opens the untouched vanilla pause menu;
8. dialogue/cutscene audio and scripted progression resume coherently.

See [docs/TESTING.md](docs/TESTING.md).

## Documentation

- [docs/DESIGN.md](docs/DESIGN.md) — state/input architecture;
- [docs/RESEARCH.md](docs/RESEARCH.md) — confirmed retail findings and failures;
- [docs/TESTING.md](docs/TESTING.md) — Xbox Store 1.5.6 acceptance procedure;
- [docs/RETAIL_TEST1.md](docs/RETAIL_TEST1.md) — retail profile / candidate provenance;
- [docs/RELEASE.md](docs/RELEASE.md) — CI and GitHub Release flow;
- [docs/PURE_PROFILE_PLAN.md](docs/PURE_PROFILE_PLAN.md) — implementation stages.
