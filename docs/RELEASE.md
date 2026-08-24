# Release pipeline

Clean Pause uses a source-controlled GitHub release flow:

```text
implementation PR
  -> Validate CI
  -> merge to main
  -> release PR changes VERSION
  -> Validate CI
  -> merge to main
  -> GitHub Actions builds tagged native artifact
  -> GitHub Release + ZIP + SHA256SUMS.txt
```

Generated DLL/ZIP files are never committed.

## Active release source

After `v0.1.0-rc.3` proved that retail Lua does not expose the required `Game.PauseGame`, the distributable implementation is native Windows code under:

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

The old profile/Lua source remains in the repository as documented prototype history, but the release workflow no longer packages it.

## Validation

PR CI has two independent jobs:

1. Linux source/tests:
   - repository unit tests;
   - historical Lua syntax;
   - permanent input-safety rules;
   - direct native pause contract and pinned KCD2 1.5.6 slot-13 checks.
2. Windows x64 native build:
   - configure/build with MSVC;
   - build `version.dll`;
   - validate required version-proxy exports;
   - reject dynamic MSVC runtime dependencies;
   - upload the compiled DLL as a short-lived CI artifact.

The native build statically links the MSVC runtime and pins MinHook to `v1.3.4` through CMake FetchContent.

## Publication

`.github/workflows/release.yml` runs on a `VERSION` change reaching `main` or a matching `v*` tag. It:

1. resolves `VERSION` and requires matching `v<VERSION>`;
2. runs source contract/tests;
3. builds native x64 Release on a Windows GitHub runner;
4. validates the produced `version.dll` exports/dependencies;
5. creates a ZIP containing only:

```text
version.dll
INSTALL.txt
```

6. writes `SHA256SUMS.txt`;
7. uploads the exact release files as a GitHub Actions artifact;
8. refuses to overwrite an existing Release;
9. creates/verifies the tag on the validated merge commit;
10. publishes the GitHub Release.

A version containing `-` is marked prerelease. A plain semantic version such as `0.1.0` is stable.

## Release assets

```text
kcd2-clean-pause-v<VERSION>.zip
SHA256SUMS.txt
```

There is no release-time GitHub Secret and no dependency on a developer machine or a user's game installation.

## KCD2 version support

The native ABI is intentionally pinned to KCD2 **1.5.6**. Runtime installation is fail-open: the environment locator requires the expected ScriptSystem/Input/System shape and an executable `IGameFramework` pause vfunc at slot 13 before the input hook is installed.

Supporting a new KCD2 version requires a reviewed implementation PR that revalidates the ABI/input assumptions, followed by the normal `VERSION` release PR. Do not silently reuse the 1.5.6 ABI after a game update.
