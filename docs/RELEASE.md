# Release pipeline

Clean Pause uses a source-controlled GitHub release flow:

```text
implementation PR
  -> Validate CI + Release build/package CI
  -> merge to main
  -> release PR changes VERSION
  -> CI
  -> merge to main
  -> Windows build/validate/package job
  -> Linux verify/publish job
  -> GitHub Release + ZIP + SHA256SUMS.txt
```

Generated DLL/ZIP files are never committed.

## Active release source

The current distributable/diagnostic implementation is native Windows code under:

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

The old profile/Lua source remains in the repository as documented prototype history, but the release workflow does not package it.

`v0.1.0-rc.4` is a failed retail candidate. Its direct native pause ABI is not a supported release contract: KCD2 1.5.6 `gEnv + 0x98` is `IGame*`, not `IGameFramework*`, so rc.4 invoked `IGame::GetName()` as if it were PauseGame and then incorrectly entered an input-swallow state.

The next diagnostic candidate (`rc.5`) keeps the native input/script bridge but removes the inferred pause vfunc entirely. Escape/Start remain vanilla and F10 probes retail Lua pause bindings.

## Validation

PR CI has two independent jobs:

1. Linux source/tests:
   - repository unit tests;
   - historical Lua syntax;
   - permanent input-safety rules;
   - rejection of the rc.4 `IGameFramework`/slot-13 pause contract;
   - corrected `gEnv + 0x98 = IGame*` ABI fact;
   - rc.5 F10-only probe contract;
   - explicit proof that native hook source does not reference Escape/Xbox Start.
2. Windows x64 native build:
   - configure/build with MSVC;
   - build `version.dll`;
   - validate required version-proxy exports;
   - reject dynamic MSVC runtime dependencies;
   - upload the compiled DLL as a short-lived CI artifact.

`.github/workflows/release.yml` also runs its real Windows build/package job on matching pull requests. The publish job is hard-disabled for `pull_request`, so the release workflow itself must parse and build successfully before merge.

The native build statically links the MSVC runtime and pins MinHook to `v1.3.4` through CMake FetchContent.

## Publication

`.github/workflows/release.yml` runs when `VERSION` reaches `main`, on a matching `v*` tag, when the release workflow itself changes, or by explicit `workflow_dispatch` retry.

Publication is split across two operating systems:

1. **Windows build job** (15-minute hard timeout)
   - resolves `VERSION` and `v<VERSION>`;
   - runs repository tests and source contracts;
   - builds native x64 Release with MSVC;
   - validates `version.dll` exports/dependencies;
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
   - runs `unzip -t` on the exact ZIP;
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

The runtime locator remains intentionally pinned to verified KCD2 **1.5.6** `SSystemGlobalEnvironment`, ScriptSystem, Input and IGame layout facts. rc.5 does **not** infer or call an `IGameFramework` pause vfunc.

Supporting a new KCD2 version requires a reviewed implementation PR that revalidates those ABI/input assumptions, followed by the normal `VERSION` release PR. Do not silently reuse 1.5.6 ABI facts after a game update.
