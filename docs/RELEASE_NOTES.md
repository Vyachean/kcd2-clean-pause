# KCD2 Clean Pause v0.3.0-rc.3

Third release candidate for **Kingdom Come: Deliverance II 1.5.6** multi-store compatibility on Windows.

The first Steam test established that build detection and canonical `gEnv` resolution were correct and eliminated the old crash. A comparison with working libKCD2/KCSE native mods then exposed the remaining root cause: Clean Pause's profiled bootstrap incorrectly treated `IGame` vtable slot 16 as `IGameFramework` on Steam. Detailed Steam 1.5.6 reverse-engineering identifies that slot as a different engine-root object. Working mods obtain the real framework from the `CCryAction` singleton instead.

RC3 corrects that framework identity assumption and restores the mature runtime's original capability boundary: the optional PauseGame observer must never prevent the input/Menu fallback from loading.

## What changed since rc.2

- Exact-profile Steam/GOG/Epic readiness no longer requires `IGame[16]` to behave as `IGameFramework`.
- Steam 1.5.6 resolves the real `IGameFramework` from the documented `CCryAction` singleton storage at `WHGame + 0x0549D328`.
- The Steam singleton is accepted only when its vtable matches the documented Steam 1.5.6 framework vtable and `IGameFramework::GetISystem()` returns the same `ISystem` as canonical `gEnv`.
- The PauseGame observer remains optional. If framework capability is unavailable, Clean Pause still installs its `PostInputEvent` hook and uses the existing verified Menu-visible fallback.
- GOG/Epic no longer fall back to interpreting `IGame[16]` as framework; their input/Menu path remains available while a canonical framework locator is not registered.
- Xbox / Microsoft Store retains the already runtime-tested legacy framework path unchanged.
- The rc.2 lifetime-readiness behavior remains as a secondary robustness measure, but it is no longer relied upon as the Steam fix.

## Compatibility status

- **Xbox / Microsoft Store 1.5.6:** Clean Pause runtime-tested baseline.
- **Steam 1.5.6 release_1_5-15693:** exact profile/canonical environment confirmed by the reporter; RC3 contains the targeted framework-identity fix and is the current acceptance candidate.
- **GOG 1.5.6 release_1_5-15693:** compatibility profile implemented; input/Menu fallback does not depend on the invalid slot-16 assumption; Clean Pause-specific smoke QA remains pending.
- **Epic Games Store 1.5.6 release_1_5-15693:** compatibility profile implemented; input/Menu fallback does not depend on the invalid slot-16 assumption; Clean Pause-specific smoke QA remains pending.

Unknown or mismatched builds remain fail closed and receive no version-specific Clean Pause hooks.

## Steam smoke test requested

For the reported Steam 1.5.6 build:

1. install the ASI package using the included INSTALL.txt;
2. launch the game and load into gameplay;
3. press Escape and confirm Clean Pause keeps the current gameplay view/HUD/subtitles visible;
4. press Escape again and confirm the ordinary vanilla pause menu appears;
5. if using an Xbox controller, repeat with Start and verify B reveals the vanilla pause menu from Clean Pause;
6. resume normally and confirm gameplay continues;
7. if anything fails, attach `kcd2_clean_pause_native.log` from beside `KCD2CleanPause.asi`.

A successful log should now show the runtime profile becoming active and, on Steam, normally show the canonical `IGameFramework::PauseGame` observer as active. Failure of that optional observer alone must no longer disable the input/Menu Clean Pause path.

## Published package

The GitHub prerelease publishes only:

- `kcd2-clean-pause-v0.3.0-rc.3-asi.zip`
- `SHA256SUMS.txt`

The ASI ZIP contains:

- `KCD2CleanPause.asi` — Clean Pause plugin;
- `dinput8.dll` — pinned official x64 Ultimate ASI Loader;
- `INSTALL.txt` — installation/removal instructions;
- `ASI_LOADER_SOURCE.txt` — loader provenance and hashes;
- `ULTIMATE_ASI_LOADER_LICENSE.txt` — upstream MIT license;
- `THIRD_PARTY_NOTICES.txt` — third-party notices for distributed components.

## Standalone version.dll status

A new standalone `version.dll` is not published while Defender investigation #38 remains unresolved. The standalone target continues to build and validate in CI, but it remains an internal CI artifact only.

## Promotion to stable v0.3.0

If the Steam smoke test confirms normal loading and accepted Clean Pause behavior, the accepted runtime can be promoted through a separate immutable v0.3.0 release-preparation commit. The earlier RC tags/releases remain immutable history.

The stable Nexus Mods update should be made only after that acceptance step and should use the stable v0.3.0 GitHub release artifact rather than an RC package.
