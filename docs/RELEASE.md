# Release pipeline

Clean Pause uses a conventional GitHub release flow with a source-controlled version:

```text
release PR changes VERSION
  -> CI validation
  -> merge to main
  -> GitHub Actions builds the merged commit
  -> creates v<VERSION> tag
  -> GitHub Release + downloadable ZIP
```

A pre-existing matching `v*` tag is also supported. Generated `.pak` and install ZIP files are never committed to Git.

## Self-contained release source

A release must be reproducible from its source commit. Release builds therefore do not depend on GitHub Secrets, a developer workstation, or files copied from a user's game installation at release time.

For the fixed Xbox Store / Xbox app / Game Pass **KCD2 1.5.6** target, the patched profile is stored as deterministic gzip+base64 source split into small text chunks:

```text
vendor/kcd2/xbox-1.5.6/profile.b64.parts/
  00.txt
  ...
  07.txt
```

`tools/build_release.py` verifies the SHA-256 of every chunk, the concatenated encoded source, the decompressed patched profile and the fail-safe XML contract before packaging.

Verified original retail profile SHA-256:

```text
69ad9fd618cd31961fef8eb061f3f2723997df5e0fb257ec74d0d5f555592565
```

Assembled encoded-source SHA-256:

```text
01b70dab6d8cfbdb502bfd683d4341ef9121c9a22b0440c06653e946413c9880
```

Current fail-safe patched profile SHA-256:

```text
9838db3747f7f36e0c9c281b8770bc7300998515407515b65493b8e9a9bcd14e
```

## Normal development and release flow

1. Make implementation changes in a branch and pass PR CI.
2. When a candidate is ready, open a release PR that changes `VERSION`, for example:

```text
0.1.0-rc.2
```

3. CI validates that exact release source, including a real self-contained package build.
4. Merge the release PR to `main`.
5. `.github/workflows/release.yml` observes the `VERSION` change, resolves tag `v0.1.0-rc.2`, rebuilds and validates the merged commit, then creates the tag and GitHub Release in one publication step.

A version containing `-` is published as a prerelease. A version such as `0.1.0` is published as a normal release.

Directly pushing an existing matching tag is also supported; the workflow refuses a tag that does not match the checked-out `VERSION`.

## Release workflow

The workflow:

1. resolves `VERSION` and the corresponding `v<VERSION>` tag;
2. checks Lua syntax and runs unit tests;
3. calls `python tools/build_release.py`;
4. validates the generated install ZIP;
5. creates `SHA256SUMS.txt`;
6. uploads the same files as a GitHub Actions artifact;
7. refuses to overwrite an existing GitHub Release;
8. creates the tag at the validated merge commit when needed and publishes the GitHub Release with the ZIP/checksum assets.

`tools/build_release.py` additionally verifies that the versioned KCD2 1.5.6 profile contains:

- release-only original `open_menu` / `open_pause_menu` vanilla fallbacks;
- press-only custom entry actions with exact `consoleCMD="1"`;
- the exclusive Clean Pause controls map and Start/Escape release sink;
- the mirrored retail `no_menu` restriction.

No release-specific secret or manually supplied retail file is involved.

## Asset layout

A release contains:

```text
kcd2-clean-pause-v<VERSION>.zip
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
3. regenerate the deterministic chunks and expected hashes for the new target;
4. update the expected target metadata;
5. pass PR CI;
6. bump `VERSION` in the release PR and merge it.

This keeps every published release reproducible from its source commit and makes game-version changes reviewable in normal Git history.
