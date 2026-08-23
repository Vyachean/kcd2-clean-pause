# Xbox Store 1.5.6 retail test candidate 1

This note records the provenance of the first installable Clean Pause candidate assembled for retail testing.

## Source

The candidate is built from the implementation in PR #4 (`prototype/pure-profile`) and an extracted `Libs/Config/defaultProfile.xml` from the target Xbox Store / Xbox app KCD2 installation.

The retail game file itself is intentionally **not committed** to this public repository. `defaultProfile.xml` is Warhorse game data and the official mod mechanism requires a whole-file override, so the repository stores the patch/build logic rather than redistributing the original profile.

Source-profile SHA-256 used for test candidate 1:

```text
69ad9fd618cd31961fef8eb061f3f2723997df5e0fb257ec74d0d5f555592565
```

Observed source-profile properties:

```text
profile version="0"
open_menu/open_menu             -> xboxpad="xi_start"
open_pause_menu/open_pause_menu -> xboxpad="xi_start"
overlays priority               -> 12
```

The profile contains no `actionPass` filters, so this exact candidate does not need any actionPass allow-list extension. Existing `actionFail` filters remain untouched.

## Reproducible repository path

Two supported builders now produce the same mod architecture:

- `tools/build_from_game.py` — extracts the profile from `Data/IPL_GameData.pak`;
- `tools/build_from_profile.py` — accepts an already extracted exact `defaultProfile.xml`.

The second path exists specifically so a retail candidate can be assembled from a user-supplied profile without requiring the full multi-hundred-megabyte game PAK.

Both builders use the same `tools/profile_patch.py`, runtime `src/Scripts/Mods/clean_pause.lua`, manifest and build validator.

## Candidate contents

The installable directory is:

```text
clean_pause/
  mod.manifest
  Data/
    clean_pause.pak
```

The PAK contains only:

```text
Libs/Config/defaultProfile.xml
Scripts/Mods/clean_pause.lua
```

The patched profile routes both retail Start actions to Clean Pause and adds the temporary exclusive `clean_pause_controls` map. No DLL/ASI/native loader is part of this candidate.

## Runtime acceptance still required

This candidate is not a release. Retail testing must still prove:

1. title/front-end controller input is unaffected;
2. first Start enters Clean Pause with zero visible pause-menu frame;
3. the current subtitle remains visible while paused;
4. unrelated input is isolated while clean-paused;
5. B resumes without triggering dialogue/cutscene skip/cancel actions;
6. second Start opens the real vanilla pause menu;
7. dialogue/cutscene audio and progression pause and resume coherently.

Record runtime results in the PR before changing the candidate architecture.
