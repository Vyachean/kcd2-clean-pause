# Release pipeline

GitHub Releases are the canonical distribution channel. Generated DLL/ZIP files are not committed.

## Production source

The distributable implementation is built directly from:

```text
native/
  CMakeLists.txt
  INSTALL.txt
  src/
    clean_pause_native.cpp
    clean_pause_native.h
    kcd2_abi.h
    version_proxy.cpp
    version.def
```

Experimental Lua/profile material remains only as historical research and is not packaged.

## Pull-request gates

For release-affecting PRs:

1. repository Python tests run;
2. historical Lua syntax is checked;
3. `tools/validate_native_contract.py` enforces the current native safety/architecture contract;
4. Windows MSVC builds x64 Release;
5. `version.dll` proxy exports are validated;
6. dynamic MSVC runtime dependencies are rejected;
7. `.github/workflows/release.yml` runs its real build/package job but does not publish on `pull_request`.

## Publication

When a release `VERSION` reaches `main`, `.github/workflows/release.yml`:

1. verifies `VERSION` and resolves `v<VERSION>`;
2. reruns tests and native contract validation;
3. builds x64 Release on Windows;
4. packages exactly:

```text
version.dll
INSTALL.txt
```

5. writes `SHA256SUMS.txt`;
6. uploads the exact package as an Actions artifact;
7. downloads and re-verifies that artifact in the publish job;
8. creates the matching GitHub Release and tag on the exact workflow commit.

Plain semantic versions such as `0.1.0` are stable. Versions containing `-` are prereleases.

## Release assets

```text
kcd2-clean-pause-v<VERSION>.zip
SHA256SUMS.txt
```

The current release notes are sourced from `docs/RELEASE_NOTES.md`.

## Version support

v0.1.0 is pinned to KCD2 **1.5.6** ABI facts verified during development. A future KCD2 update requires revalidation before claiming support; fixed offsets/semantics must not silently be assumed compatible.
