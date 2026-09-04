# Current status and plan

## Release status

- **Stable public release:** v0.2.2 ASI.
- **Published GitHub prerelease:** v0.3.0-rc.4 ASI.
- **Prepared candidate:** v0.3.0-rc.5.
- **Steam 1.5.6 `release_1_5-15693`:** exact-profile runtime accepted.
- **Xbox / Microsoft Store 1.5.6:** exact-profile runtime accepted.
- **GOG / Epic Games Store 1.5.6:** exact environment profiles implemented; Clean Pause-specific smoke QA pending.
- **Standalone version.dll:** built and validated in CI; new public distribution withheld.
- **Public rc.5 / stable v0.3.0:** blocked by Defender / Smart App Control issue #38.

Nexus remains on stable v0.2.2 while #38 is unresolved.

## Accepted architecture

The current runtime has one shared Clean Pause input/state/presentation implementation. Build-specific evidence is expressed through `BuildProfile`: build identity, ABI profile, environment locator, optional framework locator, and runtime/presentation capabilities. Shared behavior does not decide based on Steam/Xbox storefront identity.

### Steam 1.5.6

- exact PE fingerprint `0x6a350e20 / 0x05b2d000 / 0`;
- canonical `gEnv` RVA `0x0492D7F8` plus independent anchor cross-check;
- canonical framework pointer storage RVA `0x0549D328`;
- expected framework vtable RVA `0x040472D0`;
- lazy PauseGame observer on validated Pause input;
- profile root-HUD pin and Menu-prehide capabilities.

### Xbox / Microsoft Store 1.5.6

- exact PE fingerprint `0x6a391f7b / 0x05bf2000 / 0`;
- `gEnv` RVA `0x049D6EF8`;
- static `IGameFramework` object RVA `0x056EC680`;
- expected framework vtable RVA `0x040DAF18`.

The legacy writable-memory environment scan and historical `IGame[16]` framework adapter are removed from production.

### Conservative release_1_5 fallback

For an otherwise-unmatched build, fallback is considered only when build metadata matches `release_1_5-<numeric assembly id>`.

It derives `gEnv` from unique executable anchor evidence, requires full live release_1_5 ABI validation, installs no version-specific framework/PauseGame observer, enables no exact-profile presentation quirks, rejects ambiguous evidence, and rejects other ABI branches.

A forced-fallback test on the known Xbox 1.5.6 binary resolved the same `gEnv` RVA and completed repeated Clean Pause cycles.

## Runtime acceptance

Steam and Xbox final exact-profile smoke tests passed repeated Clean Pause -> vanilla pause menu -> resume cycles. Exact framework observers were active on both accepted paths. Early/unready state continues to fail open to vanilla behavior.

## Safety contract

1. KCD2 remains the sole logical pause owner.
2. Exact profile data is used only behind matching build identity.
3. Framework/PauseGame observation is optional and independently validated.
4. Exact framework roots require the expected vtable and `GetISystem() == gEnv->pSystem`.
5. Compatibility fallback is limited to the already-implemented release_1_5 ABI family.
6. Fallback borrows no known-build framework roots or presentation quirks.
7. Ambiguous/incompatible evidence leaves vanilla behavior untouched.
8. Native hooks are process-lifetime state; hot DLL unload/reload is unsupported.
9. Retail controller IDs remain authoritative: `xi_start=516`, `xi_a=526`, `xi_b=527`.

## Release blocker #38

Runtime acceptance is complete enough to assemble RC5, but public native publication remains blocked by security/reputation evidence.

Until #38 is resolved: do not promote stable v0.3.0; do not require users to disable Defender/Smart App Control or add exclusions; do not use packing/obfuscation/renaming as evasion; keep standalone publication disabled; submit the exact frozen candidate intended for publication to Microsoft Security Intelligence and record its submission ID/verdict.

## Remaining work

- #45: physical private C++ API split between bootstrap/profile resolution and the shared Clean Pause core.
- #52: residual non-blocking single-frame Steam presentation issue.
- GOG/Epic Clean Pause-specific runtime smoke.
- #38: Microsoft / Smart App Control review before public native promotion.
