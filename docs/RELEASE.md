# Release pipeline

GitHub Releases are the canonical distribution channel. Generated native binaries/ZIP files are not committed.

## Versioning policy

The project follows Semantic Versioning with a conventional GitHub tag/release flow.

- Stable releases use `vMAJOR.MINOR.PATCH`, for example `v0.2.0`.
- Prereleases use the target version plus a standard identifier, normally `v0.2.0-rc.1`.
- Before `1.0.0`, backward-compatible user-facing features increment **MINOR** (`0.1.0` -> `0.2.0`).
- Backward-compatible fixes increment **PATCH** (`0.2.0` -> `0.2.1`).
- A release candidate number increments only when another candidate for the **same target release** is needed (`0.2.0-rc.1` -> `0.2.0-rc.2`). It is not incremented for every merged PR.
- Merged work that has not been released is recorded under `Unreleased` in `CHANGELOG.md`.
- Published tags and releases are immutable history: never move, recycle, or renumber them.

The historical `v0.1.1-rc.1` through `v0.1.1-rc.4` releases predate this policy. They remain available so existing links are not broken, but no stable `v0.1.1` is planned. Their accumulated feature work targets `v0.2.0`.

## Production source

Both editions compile the same Clean Pause runtime from `native/src/clean_pause_native.cpp`.

The edition-specific bootstrap files are:

```text
ASI edition
  native/src/asi_entry.cpp

Standalone edition
  native/src/version_proxy.cpp
  native/src/version.def
```

Installation text is also edition-specific:

```text
native/INSTALL_ASI.txt
native/INSTALL_VERSION_DLL.txt
```

Experimental Lua/profile material remains only as historical research and is not packaged.

## Pull-request and main-branch gates

For release-affecting PRs and matching changes merged to `main`:

1. repository Python tests run;
2. `tools/validate_native_contract.py` enforces the current native safety/architecture contract;
3. Windows MSVC builds both x64 Release targets;
4. the standalone `version.dll` proxy exports are validated;
5. both native images are verified as x64 and dynamic MSVC runtime dependencies are rejected;
6. `.github/workflows/release.yml` produces the real release-shaped Actions artifact;
7. **no GitHub Release is published from a PR, a normal `main` push, or manual workflow dispatch.**

This lets `main` advance normally without manufacturing a new public version for every merged change.

## Preparing a release

1. Decide the next SemVer target from the changes since the previous stable release.
2. If external validation is still required, use `X.Y.Z-rc.N`; otherwise use stable `X.Y.Z`.
3. In a release-preparation PR:
   - set `VERSION` to the exact target version;
   - move the relevant `CHANGELOG.md` entries from `Unreleased` into that version;
   - update `docs/RELEASE_NOTES.md` for that version.
4. Merge the release-preparation PR after CI is green.
5. Create and push the exact tag `v<VERSION>` on that merge commit.

The tag push is the publication event.

## Publication

On a matching `v*` tag, `.github/workflows/release.yml`:

1. verifies that the tag exactly matches `VERSION`;
2. reruns tests and native contract validation;
3. builds both x64 native editions on Windows;
4. packages exactly two ZIP assets:

```text
kcd2-clean-pause-v<VERSION>-asi.zip
  KCD2CleanPause.asi
  INSTALL.txt

kcd2-clean-pause-v<VERSION>-version-dll.zip
  version.dll
  INSTALL.txt
```

5. writes one `SHA256SUMS.txt` covering both ZIPs;
6. uploads the exact files as an Actions artifact;
7. downloads and re-verifies checksums, ZIP integrity, and exact ZIP contents;
8. verifies that the existing tag points at the workflow commit;
9. creates the corresponding GitHub Release without moving or creating the tag.

A version containing `-alpha.N`, `-beta.N`, or `-rc.N` is published as a GitHub prerelease. A plain `X.Y.Z` version is published as stable.

## Edition policy

The ASI and standalone editions are mutually exclusive installations of the same runtime. They must not be installed together.

- Prefer the ASI edition when the user already has a compatible ASI loader or another mod owns `version.dll`.
- Keep the standalone `version.dll` edition for users who want a self-contained installation and have no conflicting `version.dll` mod.

See [DUAL_PACKAGE.md](DUAL_PACKAGE.md) for the packaging contract.

## Version support

The runtime remains pinned to KCD2 **1.5.6** ABI facts verified during development. A future KCD2 update requires revalidation before claiming support; fixed offsets/semantics must not silently be assumed compatible.

The standalone loading path is already retail-proven on the primary Xbox Store target. The ASI loading path requires its own retail acceptance before a stable release claims parity; see [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md).
