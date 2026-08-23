# Xbox Store 1.5.6 retail test candidate 1

This note records the provenance and release contract for the first installable Clean Pause candidate intended for retail testing.

## Original retail source

The target profile was extracted from the Xbox Store / Xbox app KCD2 1.5.6 installation.

Original retail profile SHA-256:

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

The profile contains no `actionPass` filters, so this exact target does not need any actionPass allow-list extension. Existing `actionFail` filters remain untouched.

## Repository release source

For releases, `tools/profile_patch.py` was applied to that verified retail profile and the resulting **patched** target profile is versioned with the mod source as deterministic gzip+base64 text at:

```text
vendor/kcd2/xbox-1.5.6/defaultProfile.clean-pause.xml.gz.b64
```

Decoded/decompressed patched-profile SHA-256:

```text
28e210454d749869b1fa26d4414ba3c055157e731856f9610d6ffce5ddfbc373
```

This makes a release self-contained and reproducible from its Git tag. GitHub Actions does not need a user's game installation or a repository secret.

The encoded profile is target release source, not a generated install package. Generated `.pak` and install `.zip` files remain excluded from Git.

## Build paths

Development helpers:

- `tools/build_from_game.py` — extracts and patches `Data/IPL_GameData.pak` from an installation;
- `tools/build_from_profile.py` — patches an already extracted exact retail `defaultProfile.xml`.

Canonical release builder:

- `tools/build_release.py` — decodes, verifies and packages the versioned patched Xbox 1.5.6 source.

`.github/workflows/validate.yml` exercises the release builder on PRs. `.github/workflows/release.yml` runs from version tags and attaches the resulting package to GitHub Releases.

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

The first tagged build should be published as a prerelease (for example `v0.1.0-rc.1`), not as a stable release. Retail testing must still prove:

1. title/front-end controller input is unaffected;
2. first Start enters Clean Pause with zero visible pause-menu frame;
3. the current subtitle remains visible while paused;
4. unrelated input is isolated while clean-paused;
5. B resumes without triggering dialogue/cutscene skip/cancel actions;
6. second Start opens the real vanilla pause menu;
7. dialogue/cutscene audio and progression pause and resume coherently.

Record runtime results in the PR before promoting the candidate to a stable release.
