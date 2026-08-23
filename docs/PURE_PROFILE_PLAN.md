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

The same routes and `overlays` priority 12 were confirmed in the actual extracted Xbox Store 1.5.6 profile selected for retail test candidate 1. See `docs/RETAIL_TEST1.md`.

### 2. Exact-profile builders — complete

Two repository-owned source paths are supported:

- `tools/build_from_game.py` reads the target installation's `Data/IPL_GameData.pak`;
- `tools/build_from_profile.py` accepts an already extracted exact `defaultProfile.xml` when the full game PAK is too large to transfer.

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

The map has a Start handoff action, a B-press sink and a B-release resume action. Relevant existing `actionPass` filters are extended; existing `actionFail` restrictions are preserved. The exact retail profile selected for test candidate 1 contains no `actionPass` filters.

### 5. Static validation — complete

CI covers Lua syntax, exact-profile patch unit tests, both routed Start actions, overlay-priority/exclusive controls, B press/release contract, actionPass extension, forbidden runtime mutation checks, extracted-profile preparation and a synthetic exact-profile build.

Synthetic artifacts are never published as retail packages.

### 6. CI packaging / GitHub Releases — implemented

`.github/workflows/release.yml` is the canonical public packaging path.

The exact Xbox Store 1.5.6 source profile is not committed to Git. It is supplied to Actions as gzip+base64 through the protected repository secret `KCD2_XBOX_156_DEFAULT_PROFILE_GZIP_B64`. The workflow verifies its SHA-256 before building, runs the repository builder, validates the outer ZIP and inner PAK, creates checksums, uploads a CI artifact and publishes a GitHub Release asset.

See `docs/RELEASE.md`.

### 7. Xbox Store 1.5.6 retail acceptance — next

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

`defaultProfile.xml` is a whole-file conflict point. Never commit a copied retail profile or generated install package. Build from the exact verified source profile; test without another mod replacing `defaultProfile.xml`; document manual merging if this becomes the release implementation.

## Native fallback criteria

Revisit native code only if retail testing proves that a required behaviour cannot be achieved through this official path, especially input isolation, menu handoff, zero-overlay entry, or subtitle/frame retention.
