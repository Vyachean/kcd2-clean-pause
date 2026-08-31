# Runtime compatibility model

KCD2 Clean Pause ships one native runtime. Native compatibility is selected from evidence about the actual KCD2 build rather than by assuming that every PC storefront has the same `WHGame.dll`.

## Known PC storefronts

The current PC game is distributed through four binary storefronts:

- Steam
- Epic Games Store
- GOG
- Xbox / Microsoft Store (Xbox app / Microsoft Store PC build)

Third-party key retailers are not separate runtime targets when they ultimately activate one of the storefronts above.

Steam, GOG and Epic have separate public `release_1_5-15693` Address Library mappings. Clean Pause also has its own retail Xbox / Microsoft Store 1.5.6 capture. Storefront, shipped build identity, ABI and runtime object discovery are therefore modeled separately.

## Architecture

Compatibility has five independent concepts.

### Storefront

`Storefront` identifies where a binary was distributed. Storefront alone never selects offsets, vtable slots or hooks.

Steam/GOG/Epic can be detected from independent binary markers used by KCD2/KCSE tooling (`steam_api64.dll`, `Galaxy64.dll`, `EOSSDK-Win64-Shipping.dll`). Xbox / Microsoft Store remains covered by its exact captured PE identity.

### Build identity strategy

A build may be identified using the strongest independently available evidence for that distribution.

Current strategies:

- `ExactPeFingerprint` — exact `TimeDateStamp`, `SizeOfImage` and `CheckSum`; used for the captured Steam and Xbox / Microsoft Store builds;
- `StorefrontBuildCode` — storefront marker plus Warhorse build code derived from `whdlversions.json` (`Branch.Name` + `Assembly.Id`). This is the same shipped-build identity model used by KCSE to select distribution-specific Address Libraries. It is used for GOG/Epic where the public RE corpus identifies the build and exact engine RVA but does not publish the complete PE optional-header tuple.

`StorefrontBuildCode` is not sufficient by itself to install hooks. The selected profile must still resolve and verify its exact expected `gEnv` RVA and pass every runtime ABI/identity gate below. Epic also requires its independently observed PE timestamp.

### BuildProfile

A `BuildProfile` represents a supported shipped build and contains:

- storefront metadata;
- build identity strategy and corresponding evidence;
- optional required timestamp;
- exact expected canonical `gEnv` RVA when public cross-distribution RE provides one;
- environment locator strategy;
- selected ABI profile;
- evidence / validation level.

A storefront name or user-visible game version alone is never enough.

### AbiProfile

An `AbiProfile` describes the binary contract used by Clean Pause independently of absolute addresses or storefront packaging. It contains:

- `SSystemGlobalEnvironment` field layout;
- vtable slots used by input, game framework, script and Flash UI paths;
- `InputEvent` layout and key IDs;
- Flash display-info layout;
- `C_UIHudMask` / `C_UIHudBubbles` class-layout facts used by presentation preservation.

Steam, Epic, GOG and Xbox / Microsoft Store 1.5.6 map to the same documented `release_1_5` ABI family. They therefore do not need separate copies of the mature pause/HUD implementation.

### EnvironmentLocatorStrategy

Finding the concrete engine objects is separate from their ABI.

Current strategies:

- `CanonicalPConsoleCodeAnchor` — resolves canonical `gEnv` from the `exec autoexec.cfg` code path and RIP-relative `pConsole` storage, applies the selected ABI's `pConsole` offset, and then requires the result to match the profile's independently known `gEnv` RVA;
- `LegacyXbox156ValidatedScan` — preserves the already runtime-proven Xbox / Microsoft Store 1.5.6 discovery path, but only behind its exact build identity and the stronger identity checks added by the profiled bootstrap.

A future build can reuse an existing ABI while selecting a different locator, or reuse a locator while selecting a different ABI.

## Current release_1_5 profiles

| Storefront | Build identity | Additional exact evidence | ABI | Clean Pause validation |
| --- | --- | --- | --- | --- |
| Steam | exact PE `0x6a350e20 / 0x05b2d000 / 0` | canonical `gEnv` RVA `0x492D7F8` | release_1_5 | static RE + automated resolver/build validation; final in-game smoke QA desirable |
| GOG | `Galaxy64.dll` marker + `release_1_5-15693` | canonical `gEnv` RVA `0x49177F8` | release_1_5 | public cross-distribution RE + external real-install runtime evidence; Clean Pause smoke QA still desirable |
| Epic Games Store | `EOSSDK-Win64-Shipping.dll` marker + `release_1_5-15693` | timestamp `0x6A34F917` + canonical `gEnv` RVA `0x491D8B8` | release_1_5 | public cross-distribution RE + external real-install runtime evidence; Clean Pause smoke QA still desirable |
| Xbox / Microsoft Store | exact PE `0x6a391f7b / 0x05bf2000 / 0` | mature captured runtime path | release_1_5 | runtime tested on 1.5.6 |

The GOG/Epic profiles deliberately do not invent missing `SizeOfImage` or `CheckSum` values. Instead they combine independently available shipped-build evidence with exact distribution-specific engine RVAs and strong live object validation.

## Why GOG/Epic do not require an invented PE fingerprint

The public KCSE ecosystem identifies a shipped KCD2 build by distribution plus Warhorse build code and selects a separate Address Library such as:

- `kcd_addresslib_steam_release_1_5-15693.bin`
- `kcd_addresslib_gog_release_1_5-15693.bin`
- `kcd_addresslib_epic_release_1_5-15693.bin`

Public cross-distribution analysis independently maps canonical `gEnv` for the same build family to:

- Steam: `0x492D7F8`
- GOG: `0x49177F8`
- Epic: `0x491D8B8`

The GOG and Epic mappings were cross-validated through the distribution-specific binaries rather than inferred from Steam. The public Address Libraries also have independent distribution identifiers and hashes. KCD2Online audits native REL::ID coverage against all three tables.

This gives Clean Pause several independent gates. Requiring a made-up or unverified PE field would add the appearance of precision without adding real evidence.

## Fail-closed rules

Before any version-specific hook is installed:

1. `WHGame.dll` must select a registered `BuildProfile` using that profile's identity strategy.
2. Storefront/build-code profiles must match both the binary distribution marker and the Warhorse shipped build code; any required timestamp must also match.
3. The build must select an `AbiProfile` understood completely by the mature runtime adapter.
4. Environment discovery must succeed using the build's locator strategy.
5. If the profile has an expected canonical `gEnv` RVA, the resolved object must be at exactly that RVA.
6. The resolved main-thread ID must belong to the current process.
7. `IGame::GetName()` must identify `kcd2`.
8. `IGame -> IGameFramework -> ISystem` must resolve back to the same `ISystem` as `gEnv`.

Any failure leaves vanilla behavior in control and installs no version-specific input hook.

## Adding another build

For another binary from Steam, Epic, GOG, Xbox / Microsoft Store, or a future storefront:

1. collect independently trustworthy shipped-build identity evidence;
2. use an exact PE fingerprint when the complete tuple is known, otherwise use a distribution/build identity only when it can be combined with an independent exact engine anchor/RVA;
3. determine which existing `AbiProfile` it matches, or add a new ABI profile;
4. select or implement an environment locator strategy;
5. add one `BuildProfile` row and fail-closed tests for every identity component;
6. complete in-game smoke QA before advertising Clean Pause itself as runtime-tested on that build.

If the ABI differs, describe it in a new `AbiProfile`. Do not add storefront-specific conditions to the mature pause/HUD logic. If the current adapter cannot represent the new ABI, `MatureRuntimeSupports()` must reject it until the adapter is deliberately extended.

## Evidence sources

The release_1_5 ABI and Steam/GOG/Epic cross-distribution mapping are independently documented by the public `F02K/libKCD2` and `F02K/Address-Library-For-KCSE` projects. The latter publishes separate Steam, GOG and Epic `release_1_5-15693` address libraries and cross-validates their RTTI/vtable mappings.

`F02K/KCD2Online` vendors those three tables, records their independent distribution IDs, entry counts and SHA-256 identities, and audits native REL::ID coverage against every table. Public KCSE runtime logs also confirm Epic `release_1_5-15693` with timestamp `0x6A34F917`; independent native-mod reports confirm working GOG and Epic 1.5.6 installs.
