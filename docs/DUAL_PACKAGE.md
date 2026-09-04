# Dual native packages

KCD2 Clean Pause builds the same native runtime in two mutually exclusive editions.

## ASI edition

```text
kcd2-clean-pause-v<VERSION>-asi.zip
  KCD2CleanPause.asi
  dinput8.dll
  INSTALL.txt
  ASI_LOADER_SOURCE.txt
  THIRD_PARTY_NOTICES.txt
  ULTIMATE_ASI_LOADER_LICENSE.txt
```

The release package includes the exact x64 Ultimate ASI Loader used by the supported retail path. The release workflow downloads it directly from the official `ThirteenAG/Ultimate-ASI-Loader` tagged release, pins the upstream version/source commit, verifies the published archive SHA-256 before extraction, verifies that the bundled `dinput8.dll` is x64, and records both archive and extracted-file provenance in `ASI_LOADER_SOURCE.txt`.

For a fresh installation, the bundled `dinput8.dll` and `KCD2CleanPause.asi` are installed together beside the KCD2 executable / `WHGame.dll`.

A user who already has a compatible `dinput8.dll` for other ASI plugins should keep that loader rather than overwrite it. `KCD2CleanPause.asi` must then be installed in a plugin location that the existing loader actually scans. With Ultimate ASI Loader, the simplest shared-loader layout is to place the ASI beside the existing `dinput8.dll`; its `scripts/` and `plugins/` directories are also supported.

The bundled loader is primarily for a complete fresh installation. Shared-loader compatibility does not mean an ASI placed beside `WHGame.dll` will be discovered by a loader located in another directory unless that loader is configured to scan that location.

## Standalone version.dll edition

```text
kcd2-clean-pause-v<VERSION>-version-dll.zip
  version.dll
  INSTALL.txt
  THIRD_PARTY_NOTICES.txt
```

The standalone target includes the Windows `version.dll` proxy and requires no separate ASI loader.

## Runtime identity

Both targets compile the same runtime source set; only bootstrap/loading differs. A process-wide guard prevents accidental duplicate hook installation, but intentional dual installation is unsupported.

## Build vs publication contract

CI always builds and validates **both** editions:

- both Clean Pause images must exist, target x64 and avoid dynamic MSVC runtime dependencies;
- standalone must export the complete required 17-function Windows version API surface;
- the ASI package must obtain the pinned official Ultimate ASI Loader artifact and fail if its SHA-256 differs from the reviewed upstream release digest;
- the extracted loader must be an x64 `dinput8.dll` and the upstream MIT license/provenance files must be present;
- each ZIP must contain exactly its expected release files;
- internal Actions checksums cover both packages.

Public release assets are edition-gated. Historical v0.2.1 published only the ASI ZIP while the project was still treating Defender investigation #38 as a release gate. That policy has since changed: antivirus/reputation verdicts are not release blockers by themselves. The standalone ZIP remains a CI-only validation artifact under the current ASI-first publication policy; changing that edition policy is a separate release decision.
