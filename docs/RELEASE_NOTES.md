# KCD2 Clean Pause v0.2.1

Stable patch release for **Kingdom Come: Deliverance II 1.5.6** on Windows.

## What changed

- Fixes the visible pause-entry discontinuity from v0.2.0: Clean Pause no longer performs HUD presentation work throughout the physical Start press/release interval.
- Arms HUD/subtitle preservation only around KCD2's verified vanilla `IGameFramework::PauseGame(true, ...)` call, so the retained frame and dialogue/audio pause together instead of producing a temporary frozen picture with continuing speech.
- Prevents the pause HUD-mask transition from flashing a hidden-HUD frame while preserving KCD2 as the sole logical pause owner.
- Uses KCD2's authoritative `C_UIHudMask` state for safe vanilla-menu handoff and fail-open recovery.
- Preserves exact root `hud@0` visibility and scopes shared MinHook detours to the exact runtime HUD-mask / bubble instances.
- Adds build identity and `WHGame.dll` fingerprint logging and strengthens packaging/license validation.

## Retail acceptance

The v0.2.1 ASI candidate was exercised on the primary Xbox Store / Xbox app KCD2 1.5.6 target with an Xbox controller and the upstream Ultimate ASI Loader. The accepted behavior includes:

- Start enters Clean Pause without the normal pause menu surface;
- picture/simulation and ongoing dialogue audio pause together immediately;
- gameplay HUD/subtitles remain retained without the previous transition blink;
- the retained frame remains sharp without pause DoF blur;
- second Start or Xbox B reveals the ordinary vanilla pause menu;
- normal menu resume returns to gameplay correctly.

Compatibility with arbitrary combinations of other ASI plugins is not claimed.

## Published package

- `kcd2-clean-pause-v0.2.1-asi.zip` — supported ASI edition; requires a compatible x64 ASI loader such as the upstream Ultimate ASI Loader `dinput8.dll` build.
- `SHA256SUMS.txt` — checksum for the published ASI package.

The public v0.2.1 release intentionally contains no standalone `version.dll` asset while issue #38 remains open.

Do not intentionally install multiple Clean Pause editions at once.

## Standalone version.dll status

A v0.2.1 standalone `version.dll` is **not published**. Microsoft Defender flagged an earlier PR #34 standalone candidate as `Trojan:Win32/Wacatac.C!ml`; build provenance and static imports are consistent with a likely native-hooking false positive, but issue #38 remains unresolved. The standalone target continues to build and validate in CI, including all 17 proxy exports, but the project does not ask users to whitelist it and does not distribute the new standalone binary until that investigation is resolved.

The older v0.2.0 standalone release remains immutable history, but it does not contain the v0.2.1 pause-transition fix.

## Compatibility / safety

Runtime compatibility is claimed for KCD2 **1.5.6** only. KCD2 remains the sole pause owner; the mod observes the verified vanilla pause lifecycle and changes presentation only. Failure paths prefer an ordinary visible vanilla pause menu.
