# Runtime compatibility model

KCD2 Clean Pause ships one native runtime, but native compatibility is selected by the exact `WHGame.dll` binary rather than by assuming that every PC storefront has the same executable.

## Known PC storefronts

The current PC game is distributed through four binary storefronts:

- Steam
- Epic Games Store
- GOG
- Xbox / Microsoft Store (Xbox app / Microsoft Store PC build)

Third-party key retailers are not separate runtime targets when they ultimately activate one of the storefronts above.

Steam, GOG and Epic have separate public `release_1_5-15693` Address Library mappings. Clean Pause also has its own retail Xbox / Microsoft Store 1.5.6 capture. This is why storefront and ABI are modeled separately.

## Architecture

Compatibility has four independent concepts.

### Storefront

`Storefront` is metadata only. It identifies where a binary was distributed. It must never directly select offsets, vtable slots or hooks.

Known storefront registration is deliberately broader than supported-build registration. This lets the project represent Epic/GOG immediately without pretending that an incomplete fingerprint is safe to run.

### BuildProfile

A `BuildProfile` represents one exact `WHGame.dll` binary and contains:

- storefront metadata;
- full PE fingerprint (`TimeDateStamp`, `SizeOfImage`, `CheckSum`);
- environment locator strategy;
- selected ABI profile;
- evidence / validation level.

Only `BuildProfile` entries participate in runtime matching. A version number or storefront name alone is never sufficient.

### AbiProfile

An `AbiProfile` describes the binary contract used by Clean Pause independently of absolute addresses or storefront packaging. It contains:

- `SSystemGlobalEnvironment` field layout;
- vtable slots used by input, game framework, script and Flash UI paths;
- `InputEvent` layout and key IDs;
- Flash display-info layout;
- `C_UIHudMask` / `C_UIHudBubbles` class-layout facts used by presentation preservation.

Steam, Epic, GOG and Xbox / Microsoft Store 1.5.6 currently map to the same documented `release_1_5` ABI family. They do not therefore need separate copies of the mature pause/HUD implementation.

### EnvironmentLocatorStrategy

Finding the concrete engine objects is separate from their ABI.

Current strategies:

- `CanonicalPConsoleCodeAnchor` — resolves canonical `gEnv` from the `exec autoexec.cfg` code path and RIP-relative `pConsole` storage, then applies the selected ABI's `pConsole` offset;
- `LegacyXbox156ValidatedScan` — preserves the already runtime-proven Xbox / Microsoft Store 1.5.6 discovery path, but only behind its exact build fingerprint and the stronger identity checks added by the profiled bootstrap.

A future build can therefore reuse an existing ABI while selecting a different locator, or reuse a locator while selecting a different ABI.

## Current coverage

| Storefront | Known | release_1_5 ABI evidence | Full Clean Pause fingerprint | BuildProfile | Validation |
| --- | --- | --- | --- | --- | --- |
| Steam | yes | yes | yes | yes | static RE + automated resolver/build validation; final in-game smoke QA still desirable |
| Epic Games Store | yes | yes | not yet registered | no | fail closed |
| GOG | yes | yes | not yet registered | no | fail closed |
| Xbox / Microsoft Store | yes | yes | yes | yes | runtime tested on 1.5.6 |

Epic public runtime evidence also identifies the 1.5.6 `release_1_5-15693` timestamp, but Clean Pause intentionally does not register a timestamp-only profile. `SizeOfImage` and `CheckSum` are part of the fingerprint contract.

## Fail-closed rules

Before any version-specific hook is installed:

1. `WHGame.dll` must match an exact registered `BuildProfile`.
2. The build must select an `AbiProfile` understood completely by the mature runtime adapter.
3. Environment discovery must succeed using the build's locator strategy.
4. The resolved main-thread ID must belong to the current process.
5. `IGame::GetName()` must identify `kcd2`.
6. `IGame -> IGameFramework -> ISystem` must resolve back to the same `ISystem` as `gEnv`.

Any failure leaves vanilla behavior in control and installs no version-specific input hook.

## Adding another storefront build

For another binary from Steam, Epic, GOG, Xbox / Microsoft Store, or a future storefront:

1. capture the full PE fingerprint;
2. determine which existing `AbiProfile` it matches, or add a new ABI profile;
3. select or implement an environment locator strategy;
4. add one `BuildProfile` row;
5. add static and executable resolver tests;
6. complete in-game smoke QA before advertising runtime-tested support.

If the ABI differs, describe it in a new `AbiProfile`. Do not add storefront-specific conditionals to the mature pause/HUD logic. If the current adapter cannot represent the new ABI, `MatureRuntimeSupports()` must reject it until the adapter is deliberately extended.

## Evidence sources

The release_1_5 ABI and Steam/GOG/Epic cross-distribution mapping are independently documented by the public `F02K/libKCD2` and `F02K/Address-Library-For-KCSE` reverse-engineering projects. The latter publishes separate Steam, GOG and Epic `release_1_5-15693` address libraries and independently cross-validates their RTTI/vtable mappings.
