# Runtime compatibility model

KCD2 Clean Pause ships one native runtime. Compatibility is selected from evidence about the actual KCD2 build rather than assuming every PC storefront has identical binaries or engine roots.

## Model

`BuildProfile` owns build identity, ABI profile, environment locator, optional framework locator, and runtime/presentation capabilities. Storefront metadata alone never selects offsets or behavior.

The shared native runtime implements the verified `release_1_5` ABI for the required script/input/game/system/FlashUI/HUD paths.

## Environment locators

Exact profiles use:

- `ExactEnvironmentRva`;
- `ExactEnvironmentRvaWithAnchorValidation`.

An otherwise-unmatched `release_1_5-<numeric assembly id>` build may use `AnchorDerivedEnvironment`, which derives `gEnv` from a unique executable reference to canonical `pConsole` storage. Ambiguity is a hard failure.

## Framework locators

Exact profiles use:

- `ExactPointerStorageRva`;
- `ExactObjectRva`;
- `None`.

Both exact framework forms require the expected vtable and `IGameFramework::GetISystem() == gEnv->pSystem`. Framework observation is optional and failure disables only the stronger PauseGame barrier.

## Current release_1_5 profiles

| Storefront | Build identity | Environment | Framework | Status |
| --- | --- | --- | --- | --- |
| Steam | exact PE `0x6a350e20 / 0x05b2d000 / 0` | `gEnv` RVA `0x0492D7F8` + anchor validation | pointer storage `0x0549D328`, vtable `0x040472D0` | runtime-accepted |
| Xbox / Microsoft Store | exact PE `0x6a391f7b / 0x05bf2000 / 0` | `gEnv` RVA `0x049D6EF8` | static object `0x056EC680`, vtable `0x040DAF18` | runtime-accepted |
| GOG | `Galaxy64.dll` + `release_1_5-15693` | `gEnv` RVA `0x049177F8` | `None` | profile implemented; smoke pending |
| Epic | `EOSSDK-Win64-Shipping.dll` + `release_1_5-15693` + timestamp `0x6A34F917` | `gEnv` RVA `0x0491D8B8` | `None` | profile implemented; smoke pending |

## Steam

Steam uses canonical exact roots and an independent environment anchor cross-check. The optional framework observer is acquired lazily on validated Pause input. Steam-specific root-HUD pin and Menu-prehide behavior are explicit profile capabilities.

## Xbox / Microsoft Store

Passive diagnostics on the exact Xbox 1.5.6 binary established `gEnv` RVA `0x049D6EF8`, static `IGameFramework` object RVA `0x056EC680`, and framework vtable RVA `0x040DAF18`.

Production intentionally uses the directly observed static object. The old writable-memory environment scanner and historical `IGame[16]` framework adapter are removed from production and from the supported ABI surface.

## Conservative compatibility fallback

If no exact profile matches, fallback may run only when Warhorse metadata is exactly `release_1_5-<numeric assembly id>`.

It:
1. locates the canonical executable anchor;
2. requires a unique reference to `pConsole` storage;
3. derives `gEnv` from the verified release_1_5 layout;
4. validates required live interfaces/vtables/main-thread ownership;
5. requires observed retail game-name identity;
6. installs the shared input/Menu runtime only after all required proof succeeds.

Fallback mode has no framework locator, no PauseGame observer, no exact-profile presentation capabilities, no known-build framework/vtable RVA, and no broad writable-memory scan.

A forced fallback on the known Xbox binary resolved the same `gEnv` RVA and passed repeated Clean Pause cycles.

## Fail-closed boundary

Missing/malformed metadata, `release_1_6-*`, `release_2_*`, another ABI family, ambiguous anchor evidence, or changed release_1_5 interfaces that fail validation install no compatibility runtime.

The fallback is a bridge for the already-implemented ABI family, not arbitrary forward compatibility.

## Process lifetime

Native hook installation is process-lifetime state. `Stop()` is teardown signaling, not a complete hot-unload path. Close KCD2 before replacing/removing the native module.
