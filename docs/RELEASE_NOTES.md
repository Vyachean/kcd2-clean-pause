# KCD2 Clean Pause v0.3.0

Stable release for **Kingdom Come: Deliverance II 1.5.6** on Windows.

v0.3.0 promotes the runtime accepted through the rc.5 cycle. The stable release uses one profile-driven Clean Pause runtime, exact proven roots for the tested Steam and Xbox / Microsoft Store binaries, and a conservative fallback for otherwise-unmatched builds that still identify as the verified `release_1_5` ABI family.

## Runtime-tested

### Steam 1.5.6

- exact PE/build profile;
- canonical `gEnv` with independent anchor validation;
- canonical `CCryAction` / `IGameFramework` root;
- deferred PauseGame observer;
- repeated Clean Pause -> vanilla pause menu -> resume cycles passed.

### Xbox / Microsoft Store 1.5.6

- exact PE/build profile;
- exact `gEnv` RVA `0x049D6EF8`;
- exact static `IGameFramework` object RVA `0x056EC680`;
- framework vtable RVA `0x040DAF18`;
- repeated Clean Pause -> vanilla pause menu -> resume cycles passed.

The previous Xbox writable-memory environment scan and historical `IGame[16]` framework adapter are no longer used in production.

## Compatibility fallback

For an otherwise-unmatched build whose Warhorse metadata matches `release_1_5-<numeric assembly id>`, Clean Pause may use a conservative compatibility path.

The fallback:

1. derives `gEnv` from unique executable anchor evidence;
2. performs full live release_1_5 ABI/interface validation;
3. installs only the shared input/Menu compatibility runtime.

It deliberately does not reuse a known build's framework RVA, PauseGame observer, root-HUD pin, or Menu-prehide capability. Ambiguous evidence, malformed metadata, or another ABI branch fails closed.

A diagnostic build forced the retail Xbox 1.5.6 binary through this path and resolved the same independently known `gEnv` root while completing repeated Clean Pause cycles.

## GOG / Epic Games Store

Exact environment profiles are implemented from distribution-specific evidence, but Clean Pause-specific in-game smoke QA has not been completed by this project. They are therefore not advertised as runtime-tested in v0.3.0.

## Known behavior

- Xbox B from Clean Pause reveals the normal vanilla pause menu rather than resuming directly.
- Steam can still show a residual single visual frame during Clean Pause entry; this is non-blocking and tracked in #52.

## Antivirus / Smart App Control notice

The native ASI is currently reported by some heuristic/ML scanners, including:

- Microsoft Defender: `Program:Win32/Wacapew.C!ml`;
- Cynet: `Malicious (score: 100)`;
- Symantec: `ML.Attribute.HighConfidence`.

These detections are not, by themselves, proof that the file is malicious. KCD2 Clean Pause is open source; release binaries are produced by the repository's public GitHub Actions workflow with pinned/verified dependencies and published provenance/checksums.

Issue #38 tracks antivirus/security-product compatibility and reputation as non-blocking follow-up work. Vendor reclassification is not a prerequisite for this release.

The exact hashes of the published assets are included in `SHA256SUMS.txt`.

## Package

The public stable package is the ASI edition and contains:

- `KCD2CleanPause.asi`;
- the pinned official x64 Ultimate ASI Loader `dinput8.dll`;
- installation instructions;
- loader provenance;
- third-party license notices.

The standalone `version.dll` target continues to build and validate in CI but is not part of the current ASI-first public distribution.
