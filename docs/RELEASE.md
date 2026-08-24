# Release pipeline

Clean Pause uses a source-controlled GitHub release flow:

```text
implementation PR
  -> Validate CI
  -> merge to main
  -> release PR changes VERSION
  -> Validate CI
  -> merge to main
  -> Windows build/validate/package job
  -> Linux verify/publish job
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

`.github/workflows/release.yml` runs when `VERSION` reaches `main`, on a matching `v*` tag, when the release workflow itself changes, or by an explicit `workflow_dispatch` retry. The workflow-file trigger lets publication-pipeline fixes retry an unpublished current `VERSION` without inventing a new version number.

Publication is deliberately split across two operating systems and there is no repository-wide `main` concurrency lock between release attempts:

1. **Windows build job** (15-minute hard timeout)
   - resolves `VERSION` and `v<VERSION>`;
   - runs source contract/tests;
   - builds native x64 Release with MSVC;
   - validates the produced `version.dll` exports/dependencies;
   - creates a ZIP containing only:

```text
version.dll
INSTALL.txt
```

   - writes `SHA256SUMS.txt`;
   - uploads those exact files as an Actions artifact.
2. **Linux publish job** (5-minute hard timeout)
   - downloads the Windows-produced artifact;
   - verifies `SHA256SUMS.txt`;
   - runs `unzip -t` on the exact ZIP that will be published;
   - creates or verifies the tag on the workflow commit;
   - publishes the GitHub Release with the verified ZIP and checksum file.

If a Release for the same tag already exists, a retry leaves it unchanged instead of overwriting assets. A version containing `-` is marked prerelease. A plain semantic version such as `0.1.0` is stable.

## Release assets

```text
kcd2-clean-pause-v<VERSION>.zip
SHA256SUMS.txt
```

There is no release-time GitHub Secret and no dependency on a developer machine or a user's game installation.

## KCD2 version support

The native ABI is intentionally pinned to KCD2 **1.5.6**. Runtime installation is fail-open: the environment locator requires the expected ScriptSystem/Input/System shape and an executable `IGameFramework` pause vfunc at slot 13 before the input hook is installed.

Supporting a new KCD2 version requires a reviewed implementation PR that revalidates the ABI/input assumptions, followed by the normal `VERSION` release PR. Do not silently reuse the 1.5.6 ABI after a game update.
