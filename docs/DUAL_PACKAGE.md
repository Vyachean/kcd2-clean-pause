# Dual native packages

KCD2 Clean Pause builds the same native runtime in two mutually exclusive editions.

## ASI edition

```text
kcd2-clean-pause-v<VERSION>-asi.zip
  KCD2CleanPause.asi
  INSTALL.txt
  THIRD_PARTY_NOTICES.txt
```

Requires a compatible x64 ASI loader, normally installed as `dinput8.dll` beside the KCD2 executable / `WHGame.dll`.

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

- both images must exist, target x64 and avoid dynamic MSVC runtime dependencies;
- standalone must export the complete required 17-function Windows version API surface;
- each ZIP must contain the expected binary, install text and third-party notices;
- internal Actions checksums cover both packages.

Public release assets are edition-gated. For **v0.2.1**, only the ASI ZIP is published because Defender investigation #38 blocks distribution of the new standalone binary. The standalone ZIP remains a CI-only validation artifact until that issue is resolved.

Do not obtain/whitelist an unofficial standalone build to bypass that gate.
