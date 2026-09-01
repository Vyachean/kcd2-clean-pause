# Runtime compatibility model

KCD2 Clean Pause ships one native runtime. Compatibility is selected from evidence about the actual KCD2 build rather than by assuming every PC storefront has the same `WHGame.dll`.

## Known PC storefronts

The current PC game is distributed through four binary storefronts:

- Steam
- Epic Games Store
- GOG
- Xbox / Microsoft Store (Xbox app / Microsoft Store PC build)

Steam, GOG and Epic have separate public `release_1_5-15693` Address Library mappings. Clean Pause also has its own retail Xbox / Microsoft Store 1.5.6 capture.

## Compatibility dimensions

### Storefront

`Storefront` identifies where a binary was distributed. Storefront alone never selects offsets, vtable slots or hooks.

Steam/GOG/Epic are detected from distribution markers in loaded `WHGame.dll` `.rdata` (`steam_api64.dll`, `Galaxy64.dll`, `EOSSDK-Win64-Shipping.dll`). Xbox / Microsoft Store remains covered by its exact captured PE identity.

### Build identity

Current strategies:

- `ExactPeFingerprint` — exact `TimeDateStamp`, `SizeOfImage` and `CheckSum`; used for captured Steam and Xbox builds;
- `StorefrontBuildCode` — storefront marker plus Warhorse build code from `whdlversions.json` (`Branch.Name` + `Assembly.Id`); used for GOG/Epic together with independent exact engine-RVA evidence.

### BuildProfile

A `BuildProfile` represents a supported shipped binary and contains storefront metadata, identity evidence, environment locator, ABI profile and validation level.

### AbiProfile

`AbiProfile` describes the binary contract used by the core Clean Pause runtime independently of absolute addresses: canonical `SSystemGlobalEnvironment`, input ABI, required script/game/system/FlashUI slots, Flash display layout and HUD/Bubbles layouts.

Steam, GOG, Epic and Xbox / Microsoft Store 1.5.6 share the documented core `release_1_5` ABI used by those required paths. That does **not** imply every auxiliary accessor has identical semantics across storefront binaries.

### Environment locator

- `ExactEnvironmentRva` — canonical gEnv RVA for GOG/Epic;
- `ExactEnvironmentRvaWithAnchorValidation` — canonical Steam gEnv RVA plus one-time independent `exec autoexec.cfg -> pConsole` cross-check;
- `LegacyXbox156ValidatedScan` — existing runtime-proven Xbox discovery path behind its exact fingerprint.

For Steam/GOG/Epic, immutable build-level environment identity is resolved once. Live readiness then checks only required objects inside that known gEnv. Polling is 100 ms during the initial window and backs off to 1 second afterward.

### Optional capabilities

The `IGameFramework::PauseGame` observer is an optional optimization/barrier, not a prerequisite for the core PostInputEvent/Menu Clean Pause path.

This distinction matters on Steam 1.5.6. Earlier RCs incorrectly treated `IGame` slot 16 as a storefront-independent `IGameFramework` accessor. Detailed Steam RE identifies that slot as a different engine-root object. Working libKCD2/KCSE mods obtain real framework functionality from the `CCryAction` singleton instead.

For the exact Steam 1.5.6 build, Clean Pause therefore resolves the real framework from:

- `IGameFramework*` storage: `WHGame + 0x0549D328` (`qword_18549D328` in the public Steam RE image);
- expected framework vtable: `WHGame + 0x040472D0`;
- identity proof: `IGameFramework::GetISystem()` must equal canonical `gEnv->pSystem`.

If this optional Steam capability cannot be validated, its PauseGame hook is skipped while the required input/Menu path remains available.

The runtime-tested Xbox path keeps the legacy IGame-slot framework lookup isolated to Xbox. GOG/Epic do not fall back to that assumption; a canonical framework locator can be added for those profiles later without changing core compatibility.

## Current release_1_5 profiles

| Storefront | Build identity | Required environment evidence | Framework capability | Clean Pause validation |
| --- | --- | --- | --- | --- |
| Steam | exact PE `0x6a350e20 / 0x05b2d000 / 0` | gEnv RVA `0x492D7F8` + one-time anchor cross-check | CCryAction storage `0x0549D328`, optional but strongly validated | RC1 confirmed profile/gEnv and no crash; RC3 acceptance pending |
| GOG | `Galaxy64.dll` + `release_1_5-15693` | gEnv RVA `0x49177F8` | no canonical locator registered; Menu fallback remains available | public RE/external runtime evidence; Clean Pause smoke QA pending |
| Epic Games Store | `EOSSDK-Win64-Shipping.dll` + `release_1_5-15693` + timestamp `0x6A34F917` | gEnv RVA `0x491D8B8` | no canonical locator registered; Menu fallback remains available | public RE/external runtime evidence; Clean Pause smoke QA pending |
| Xbox / Microsoft Store | exact PE `0x6a391f7b / 0x05bf2000 / 0` | mature captured runtime path | legacy path retained only for this runtime-tested profile | runtime-tested Clean Pause 1.5.6 |

## GOG/Epic build identity

The KCSE ecosystem identifies shipped KCD2 builds by distribution plus Warhorse build code and publishes separate Address Libraries:

- `kcd_addresslib_steam_release_1_5-15693.bin`
- `kcd_addresslib_gog_release_1_5-15693.bin`
- `kcd_addresslib_epic_release_1_5-15693.bin`

Cross-distribution analysis maps canonical gEnv to:

- Steam: `0x492D7F8`
- GOG: `0x49177F8`
- Epic: `0x491D8B8`

The GOG/Epic mappings are independently cross-validated rather than inferred from Steam. Missing PE optional-header fields are therefore not invented.

## Build metadata discovery

For build-code profiles, Clean Pause reads Warhorse `whdlversions.json` and forms `<Branch.Name>-<Assembly.Id>`, e.g. `release_1_5-15693`. The lookup has a strict parent-depth bound and executable Windows path/parser fixtures. Missing/malformed/mismatched metadata leaves the profile fail closed.

## Required fail-closed gates

Before the core version-specific input hook is installed:

1. `WHGame.dll` must select a registered `BuildProfile`.
2. Every identity component required by that profile must match.
3. The selected `AbiProfile` must be fully supported by the mature adapter.
4. The profile-specific canonical environment identity must validate.
5. Steam must also pass its one-time gEnv anchor cross-check.
6. Required `IScriptSystem`, `IInput`, `IGame`, `ISystem` and `IFlashUI` surfaces must validate.
7. The main-thread ID must belong to the current process.
8. `IGame::GetName()` must identify `kcd2`.

`IGameFramework` is deliberately **not** in this required list. When a framework capability is available, its own identity gates must pass before only the optional PauseGame observer is installed.

Unknown/mismatched builds install no core version-specific hooks. Failure of an optional capability disables only that capability.

## Adding another build

For another Steam/Epic/GOG/Xbox binary or future storefront:

1. collect trustworthy shipped-build identity evidence;
2. determine/reuse the core `AbiProfile` or add a new one;
3. register the least-assumptive gEnv locator supported by evidence;
4. add required fail-closed tests;
5. add optional capability locators independently where needed (for example a framework singleton); do not promote an optional capability to a core readiness gate;
6. complete in-game Clean Pause smoke QA before calling that build runtime-tested.

## Evidence sources

The core release_1_5 ABI and Steam/GOG/Epic cross-distribution mappings are documented by public `F02K/libKCD2` / `JerryYOJ/libKCD2` and `F02K/Address-Library-For-KCSE` work. The latter publishes separate distribution-specific `release_1_5-15693` tables. `F02K/KCD2Online` audits REL::ID coverage against those tables.

For framework identity specifically, libKCD2 documents Steam `IGame[16]` as a different engine-root object, while `CCryAction::GetInstance()` resolves `REL::ID(2356)` / `qword_18549D328`; working native projects use that `CCryAction` path for `IGameFramework` functionality.
