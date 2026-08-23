# Release pipeline

Clean Pause uses a conventional GitHub release flow:

```text
source commit / PR
  -> CI validation
  -> version tag
  -> GitHub Actions build
  -> GitHub Release + downloadable ZIP
```

Generated `.pak` and install ZIP files are never committed to Git.

## Self-contained release source

A release tag must be reproducible from that tag alone. Release builds therefore do not depend on GitHub Secrets, a developer workstation, or files copied from a user's game installation at release time.

For the fixed Xbox Store / Xbox app / Game Pass **KCD2 1.5.6** target, the repository versions the already patched target profile as deterministic gzip+base64 text at:

```text
vendor/kcd2/xbox-1.5.6/defaultProfile.clean-pause.xml.gz.b64
```

This is target-specific source input, not a generated release artifact. `tools/build_release.py` base64-decodes and decompresses it to the patched `Libs/Config/defaultProfile.xml` required by the official KCD2 mod package.

Verified original retail profile SHA-256:

```text
69ad9fd618cd31961fef8eb061f3f2723997df5e0fb257ec74d0d5f555592565
```

Decoded patched profile SHA-256:

```text
28e210454d749869b1fa26d4414ba3c055157e731856f9610d6ffce5ddfbc373
```

`tools/build_release.py` verifies that digest before packaging.

## Normal development flow

1. Make implementation changes in a branch.
2. Open/update a PR.
3. `.github/workflows/validate.yml` runs Lua syntax checks, unit tests, the synthetic exact-profile proof, and the real self-contained release build.
4. Merge the approved release candidate.
5. Create a semantic version tag, for example:

```text
v0.1.0-rc.1
```

6. Push the tag.
7. `.github/workflows/release.yml` builds exactly that tagged commit and publishes the assets on GitHub Releases.

Tags containing a prerelease suffix such as `-rc.1` are published as GitHub prereleases. A tag such as `v0.1.0` becomes a normal release.

## Release workflow

The tag-triggered workflow:

1. checks out the tag;
2. checks Lua syntax and runs unit tests;
3. calls `python tools/build_release.py`;
4. validates the generated install ZIP;
5. creates `SHA256SUMS.txt`;
6. uploads the same files as a GitHub Actions artifact;
7. creates a GitHub Release with generated release notes and attaches the ZIP/checksum files.

No release-specific secret or manually supplied retail file is involved.

## Asset layout

A release contains an asset such as:

```text
kcd2-clean-pause-v0.1.0-rc.1.zip
SHA256SUMS.txt
```

The install ZIP contains:

```text
clean_pause/
  mod.manifest
  Data/
    clean_pause.pak
```

The game PAK contains:

```text
Libs/Config/defaultProfile.xml
Scripts/Mods/clean_pause.lua
```

## Supporting another KCD2 version

Because KCD2 uses last-mod-wins for `defaultProfile.xml`, supporting another retail version is a source change, not a CI parameter.

For a new target version:

1. extract that version's exact retail `defaultProfile.xml`;
2. run the repository patcher and review the result;
3. version the new patched target profile under a game-version-specific directory;
4. update the expected hash/target metadata;
5. pass PR CI;
6. tag a new release.

This keeps every published release reproducible from its Git tag and makes game-version changes reviewable in normal Git history.
