# Official-profile implementation plan

Primary target: KCD2 1.5.6, PC Xbox Store / Xbox app / Game Pass.

## Decision

Use the official KCD2 `.pak`/Lua path first. Native DLL/ASI code remains fallback-only and is not part of the current test candidate.

## Stage status

### 1. Establish exact retail Start routes — complete

Confirmed effective profile routes:

```text
open_menu/open_menu             -> xi_start
open_pause_menu/open_pause_menu -> xi_start
```

The same routes and `overlays` priority 12 were confirmed in the actual extracted Xbox Store 1.5.6 profile selected for retail testing. See `docs/RETAIL_TEST1.md`.

### 2. Exact-profile development builders — complete

Two maintainer/development source paths are supported:

- `tools/build_from_game.py` reads the target installation's `Data/IPL_GameData.pak`;
- `tools/build_from_profile.py` accepts an already extracted exact `defaultProfile.xml`.

Both fail closed unless the expected 1.5.6 structure exists and patch both retail Start actions while preserving action IDs and physical bindings.

### 3. Clean Pause state machine — complete for retail testing

```text
Running + routed Start
  -> enable clean_pause_controls
  -> Game.PauseGame(true)
  -> CleanPaused

CleanPaused + B release
  -> disable clean_pause_controls
  -> Game.PauseGame(false)
  -> Running

CleanPaused + Start
  -> disable clean_pause_controls
  -> MenuEvents.DisplayIngameMenu(true)
  -> vanilla menu owns pause lifecycle
```

### 4. Input isolation without retail `EnableActionFilter` — complete for retail testing

The old design incorrectly depended on `ActionMapManager.EnableActionFilter`, which is not in the target retail Lua method list.

Replacement:

```xml
<actionmap name="clean_pause_controls"
           priority="overlays"
           exclusivity="1">
```

The map has a Start handoff action, a B-press sink and a B-release resume action. Relevant existing `actionPass` filters are extended; existing `actionFail` restrictions are preserved. The exact retail profile selected for the first candidate contains no `actionPass` filters.

### 5. Self-contained release source — complete

KCD2 uses last-mod-wins for `defaultProfile.xml`, so the fixed 1.5.6 release needs the complete patched profile.

The patched target profile is versioned at:

```text
vendor/kcd2/xbox-1.5.6/defaultProfile.clean-pause.xml.gz
```

`tools/build_release.py` verifies the decompressed SHA-256 and packages that source together with the repository Lua/runtime and manifest.

This removes the previous GitHub Actions Secret/manual retail-file dependency. A release is reproducible from its Git tag alone.

### 6. Static validation — complete

CI covers Lua syntax, exact-profile patch unit tests, both routed Start actions, overlay-priority/exclusive controls, B press/release contract, actionPass extension, forbidden runtime mutation checks, synthetic exact-profile generation, and the real self-contained release build.

PR validation never publishes its generated package.

### 7. Tag-based GitHub Releases — implemented

`.github/workflows/release.yml` follows the normal release flow:

```text
version tag (v*)
  -> checkout tag
  -> validate
  -> tools/build_release.py
  -> ZIP + SHA256SUMS.txt
  -> GitHub Release assets
```

A tag with a suffix such as `v0.1.0-rc.1` is published as a prerelease. A stable tag such as `v0.1.0` is a normal release.

See `docs/RELEASE.md`.

### 8. Xbox Store 1.5.6 retail acceptance — next

Must prove:

1. title/front-end controller remains normal;
2. first Start enters Clean Pause with zero menu frame;
3. current subtitle remains visible;
4. overlay-priority exclusivity isolates unrelated input;
5. B resumes without dialogue/cutscene skip;
6. second Start opens the real vanilla pause menu through `MenuEvents`;
7. closing that menu returns to ordinary gameplay;
8. dialogue/cutscene/audio progression pauses and resumes coherently.

See `docs/TESTING.md`.

## Compatibility policy

`defaultProfile.xml` is a whole-file conflict point. The 1.5.6 release source is deliberately pinned to that game version. Test without another mod replacing `defaultProfile.xml`; supporting another KCD2 version requires regenerating/reviewing the versioned target profile and publishing a new tagged release.

Generated `.pak` and install `.zip` files are never tracked in Git.

## Native fallback criteria

Revisit native code only if retail testing proves that a required behaviour cannot be achieved through this official path, especially input isolation, menu handoff, zero-overlay entry, or subtitle/frame retention.
