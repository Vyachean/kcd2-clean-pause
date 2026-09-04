# KCD2 Clean Pause v0.3.0-rc.5

Fifth release candidate for **Kingdom Come: Deliverance II 1.5.6** multi-store compatibility on Windows.

RC5 consolidates the accepted Steam and Xbox runtime paths into one profile-driven architecture and adds a conservative compatibility bridge for otherwise-unmatched builds that still identify as the verified `release_1_5` ABI family.

## Highlights

- Steam 1.5.6 `release_1_5-15693` remains on its exact PE fingerprint, canonical `gEnv` RVA, independent anchor validation, and canonical `CCryAction` framework root.
- Xbox / Microsoft Store 1.5.6 no longer uses the old writable-memory `gEnv` scan or historical `IGame[16]` framework accessor.
- Runtime evidence captured from the real Xbox 1.5.6 binary established:
  - `gEnv` RVA `0x049D6EF8`;
  - static `IGameFramework` object RVA `0x056EC680`;
  - expected framework vtable RVA `0x040DAF18`.
- Both exact storefront paths converge on the same strong framework validation and the same Clean Pause state/presentation runtime.
- The production translation-unit wrapper is gone; both native editions compile the shared runtime normally.

## Conservative compatibility fallback

If an exact registered profile does not match, RC5 may attempt a fallback **only** when Warhorse build metadata has the form `release_1_5-<numeric assembly id>`.

The fallback derives `gEnv` from unique executable anchor evidence, validates the complete release_1_5 runtime, and installs only the shared input/Menu path. It deliberately does **not** reuse a known build's framework RVA, framework vtable, PauseGame observer, root-HUD pin, or Menu-prehide capability. Ambiguous evidence, malformed metadata, or another ABI branch leaves vanilla behavior untouched.

A diagnostic build forced the known Xbox 1.5.6 binary through this fallback, resolved the same `gEnv` RVA `0x049D6EF8`, and completed repeated Clean Pause -> vanilla-menu -> resume cycles.

## Runtime acceptance

**Steam 1.5.6:** exact environment/framework validated, lazy PauseGame observer active, repeated Clean Pause cycles and vanilla-menu handoff/resume passed.

**Xbox / Microsoft Store 1.5.6:** exact environment and static framework object validated, PauseGame observer active, repeated Clean Pause cycles and vanilla-menu handoff/resume passed.

**GOG / Epic Games Store:** exact environment profiles remain implemented, but Clean Pause-specific in-game smoke QA is still pending.

## Known behavior

- Xbox B from Clean Pause reveals the normal vanilla pause menu rather than resuming directly.
- Steam can still show a residual single visual frame after pause ownership is established; tracked separately in #52.

## Package and antivirus notice

The ASI package contains `KCD2CleanPause.asi`, the pinned official x64 Ultimate ASI Loader, installation instructions, provenance/hashes, upstream license, and third-party notices.

The standalone `version.dll` target is still built, validated, packaged and hashed in CI, but remains non-public under the current ASI-first edition-publication policy.

v0.3.0-rc.5 is published as a prerelease with a known antivirus/Smart App Control warning. Current reported heuristic/ML detections include:

- Microsoft Defender: `Program:Win32/Wacapew.C!ml`;
- Cynet: `Malicious (score: 100)`;
- Symantec: `ML.Attribute.HighConfidence`.

These detections are not treated as proof of malware, but neither are they ignored. The project is open source, the release is built by public GitHub Actions, dependencies are pinned, and release hashes/provenance are published so users can independently evaluate the prerelease.

Exact published asset hashes are provided in `SHA256SUMS.txt`. Vendor-review status is tracked in #38 as non-blocking compatibility/reputation work.

These antivirus/Smart App Control detections do not by themselves block stable v0.3.0. Stable promotion is governed by the project's own QA, compatibility, provenance, and release criteria.
