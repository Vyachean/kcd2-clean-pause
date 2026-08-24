# KCD2 Clean Pause

Clean Pause is an experimental **Kingdom Come: Deliverance II** mod whose target UX is:

```text
Running
  Xbox Menu / Start -> Clean Pause

Clean Pause
  B                  -> Resume
  Xbox Menu / Start  -> vanilla KCD2 pause menu
```

The product goal is to freeze gameplay/dialogue/in-engine cutscenes without covering the current rendered frame, so the current subtitle can remain visible.

## Target

- KCD2 **1.5.6**
- PC Xbox Store / Xbox app / Game Pass
- Xbox controller

## Current status

**Diagnostic prerelease development. `v0.1.0-rc.1` and `v0.1.0-rc.2` are confirmed broken.**

Retail results:

- `rc.1`: Escape and Xbox Start did nothing;
- `rc.2`: Escape and Xbox Start still did nothing.

`rc.2` disproved the assumption that changing the original KCD2 pause action to `onRelease`-only provides a usable vanilla fallback. The project will not touch Start again until the Lua/console-command layer is independently proven.

## Next diagnostic candidate

The next prerelease restores the original retail pause actions to their normal activation contract:

```text
open_menu/open_menu
open_pause_menu/open_pause_menu

onPress="1"
onRelease="1"
keyboard="_keybinds_ref_"
xboxpad="xi_start"
```

They remain non-console actions. **Escape and Xbox Start must therefore open the ordinary vanilla pause menu.**

A separate keyboard-only probe is derived at build time:

```text
F10
  -> clean_pause_probe_gameplay / clean_pause_probe_pause_context
  -> consoleCMD="1"
  -> System.AddCCommand
  -> CleanPause.Enter()
  -> Game.PauseGame(true)
```

The F10 actions have no Xbox or PlayStation binding.

If F10 clean-pauses successfully, the packed Lua bootstrap and `consoleCMD` route are proven and only Start interception remains. If F10 does nothing, the next investigation is the Lua/bootstrap/command-registration layer rather than another input remap.

## Release source

The already CI-verified Xbox 1.5.6 rc2 profile remains the single versioned source under:

```text
vendor/kcd2/xbox-1.5.6/profile.b64.parts/
```

The diagnostic profile is **derived in CI** from that verified source. `tools/profile_probe_patch.py`:

1. restores `onPress="1"` on the original `open_menu` and `open_pause_menu` actions while retaining their original release/bindings;
2. converts the rc2 custom entry slots into F10-only probe actions;
3. renames the corresponding filter references;
4. leaves the temporary `clean_pause_controls` map available only after a successful Clean Pause entry.

No second 100 KB profile copy is committed.

Verified rc2 source profile SHA-256:

```text
9838db3747f7f36e0c9c281b8770bc7300998515407515b65493b8e9a9bcd14e
```

## Distribution

GitHub Releases are the canonical distribution channel. Generated `.pak`/`.zip` files are not committed.

```text
implementation PR
  -> Validate CI
  -> merge to main
  -> release PR changes VERSION
  -> Validate CI
  -> merge to main
  -> GitHub Actions creates tag + GitHub Release
```

## Safety constraints

Clean Pause does **not**:

- call `ActionMapManager.InitActionMaps()`;
- call runtime `ActionMapManager.LoadFromXML()`;
- call `ActionMapManager.EnableActionFilter()`;
- replace `Player.OnAction`;
- persistently remap controller input;
- replace `Menu.gfx`.

`InitActionMaps()` is permanently forbidden because an earlier retail prototype broke controller input globally.

## Installation

Extract the release ZIP so this exists:

```text
%USERPROFILE%\Documents\kingdomcome_mods\clean_pause\mod.manifest
```

Disable other mods that replace `Libs/Config/defaultProfile.xml` while testing.

## Diagnostic retail test

For the next candidate only:

1. verify **Escape opens the normal vanilla pause menu**;
2. verify **Xbox Start opens the normal vanilla pause menu**;
3. return to ordinary exploration;
4. press **F10**;
5. report whether F10 freezes the world without the vanilla pause overlay;
6. if F10 does nothing, report whether `kcd.log` contains any `[Clean Pause]` lines.

Do not continue to subtitle/second-Start acceptance until the F10 probe succeeds.

See [docs/TESTING.md](docs/TESTING.md) for the exact diagnostic procedure.
