# KCD2 Clean Pause v0.2.2

Stable packaging release for **Kingdom Come: Deliverance II** on Windows.

## What changed

- Bundles the official x64 Ultimate ASI Loader with the ASI release package for a complete fresh installation.
- Pins upstream Ultimate ASI Loader **v9.7.4** together with its source commit, release asset, and SHA-256 instead of using a floating latest download.
- Verifies the upstream archive digest before extraction and validates the bundled `dinput8.dll` as x64.
- Includes `ASI_LOADER_SOURCE.txt` with provenance and `ULTIMATE_ASI_LOADER_LICENSE.txt` with the upstream MIT license.
- Keeps the shared-loader path intact: if a compatible `dinput8.dll` is already installed, keep it and copy only `KCD2CleanPause.asi`.

There is **no Clean Pause runtime behavior change from v0.2.1**.

## Tested behavior

The runtime was exercised with **KCD2 1.5.6 on the PC Xbox Store / Xbox app version**, using an Xbox controller and the upstream Ultimate ASI Loader. The accepted behavior includes:

- Start enters Clean Pause without drawing the normal pause menu;
- picture/simulation and ongoing dialogue audio pause together immediately;
- gameplay HUD and dialogue subtitles remain visible without the previous transition blink;
- active NPC overhead subtitles remain preserved;
- the retained frame remains sharp without pause depth-of-field blur;
- second Start or Xbox B reveals the ordinary vanilla pause menu;
- normal menu resume returns to gameplay correctly.

## Published package

`kcd2-clean-pause-v0.2.2-asi.zip` contains:

- `KCD2CleanPause.asi` — Clean Pause plugin;
- `dinput8.dll` — pinned official x64 Ultimate ASI Loader;
- `INSTALL.txt` — installation/removal instructions;
- `ASI_LOADER_SOURCE.txt` — loader provenance and hashes;
- `ULTIMATE_ASI_LOADER_LICENSE.txt` — upstream MIT license;
- `THIRD_PARTY_NOTICES.txt` — third-party notices for distributed components.

`SHA256SUMS.txt` contains the checksum for the public ASI package.

Do not intentionally install multiple Clean Pause editions at once.

## Standalone version.dll status

A new standalone `version.dll` is not published while Defender investigation #38 remains unresolved. The standalone target continues to build and validate in CI, but users are not asked to whitelist an unofficial or CI-only binary.

The older v0.2.0 standalone release remains immutable history and does not contain the v0.2.1 transition fix.

## Safety

KCD2 remains the sole logical pause owner. Clean Pause observes the verified vanilla pause lifecycle and changes presentation only. Failure paths prefer the ordinary visible vanilla pause menu.
