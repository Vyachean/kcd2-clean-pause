# KCD2 Clean Pause v0.3.0-rc.4

Fourth release candidate for **Kingdom Come: Deliverance II 1.5.6** multi-store compatibility on Windows.

RC3 corrected the Steam framework identity error by resolving the real `IGameFramework` from the canonical `CCryAction` singleton instead of interpreting `IGame[16]` as framework. A second comparison with working KCD2 native mods and the pinned MinHook implementation exposed one remaining lifecycle weakness: RC3 still attempted the optional Steam PauseGame observer only once during worker-thread bootstrap. If `CCryAction` had not published its singleton at that exact moment, Clean Pause would keep running through the Menu/input fallback but the stronger PauseGame barrier would remain unavailable for the rest of the process.

RC4 removes that timing dependency. The required input/Menu runtime is installed independently, while the optional Steam PauseGame observer is acquired lazily on a real Pause input after the game has reached an input-capable lifecycle stage.

## What changed since rc.3

- The required `PostInputEvent` hook is installed first and is rolled back cleanly if enabling it fails.
- Steam no longer attempts the PauseGame observer from bootstrap after the input hook becomes live.
- On a real Escape/Start press, Clean Pause resolves the canonical Steam `CCryAction` singleton and installs the optional PauseGame observer **before** forwarding that press to vanilla.
- If the framework singleton is still unavailable, the press continues through the existing Menu/input fallback and the observer is retried on a later Pause press.
- The Steam observer has one installation path, eliminating a narrow duplicate-create race between bootstrap and the first input event.
- Direct reads performed by the new profiled input wrapper are protected with SEH; an unexpected engine payload falls through to the mature runtime instead of crashing in the compatibility shim.
- Xbox / Microsoft Store retains the already runtime-tested framework path and behavior.
- GOG/Epic remain on their supported input/Menu capability path without the invalid `IGame[16]` framework assumption; Clean Pause-specific runtime acceptance is still pending.

## Cross-check completed before RC4

The runtime was rechecked against current public KCD2 1.5.6 reverse-engineering and working native-mod code. No further ABI changes were required for:

- KCD2 `SInputEvent` field offsets used by Clean Pause;
- `IInput::PostInputEvent` slot 13;
- `IGameFramework::PauseGame` slot 13 and `GetISystem` slot 19;
- `IFlashUI::GetUIElementByInstanceStr` slot 18;
- `IUIElement` Update/Render/SetVisible/IsVisible slots 23/24/28/29;
- `IUIElement::CallFunction` / `GetMovieClip` slots 69/71;
- `C_UIHudMask` and `C_UIHudBubbles` listener/interface layouts used by the mature runtime;
- `IScriptSystem::ExecuteBuffer` slot 6 and the `System.GetCVar` / `System.SetCVar` script API used by blur suppression.

Controller IDs remain intentionally based on stronger retail evidence from an actual Xbox Store KCD2 1.5.6 session: `xi_start=516`, `xi_a=526`, `xi_b=527`. These values previously fixed a real B-button bug and are not replaced by SDK-derived contiguous assumptions.

The project pins MinHook v1.3.4. Its public hook API is internally serialized, and the mature runtime already installs Menu/HUD/Mask/Bubbles hooks from the first-Pause input call stack. RC4 keeps Steam PauseGame acquisition in that established path rather than introducing a parallel hook-install worker.

## Compatibility status

- **Xbox / Microsoft Store 1.5.6:** Clean Pause runtime-tested baseline.
- **Steam 1.5.6 release_1_5-15693:** exact profile and canonical environment already confirmed by the reporter; RC4 is the current lifecycle-hardened acceptance candidate.
- **GOG 1.5.6 release_1_5-15693:** compatibility profile implemented; Clean Pause-specific smoke QA remains pending.
- **Epic Games Store 1.5.6 release_1_5-15693:** compatibility profile implemented; Clean Pause-specific smoke QA remains pending.

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

On Steam, the log should show the core runtime becoming active before framework capability is needed. On the first Pause press it should normally report the canonical `IGameFramework::PauseGame` observer becoming active. Failure of that optional observer alone must not disable the Menu/input Clean Pause path.

## Published package

The GitHub prerelease publishes only:

- `kcd2-clean-pause-v0.3.0-rc.4-asi.zip`
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

If the Steam smoke test confirms normal loading and accepted Clean Pause behavior, the accepted RC4 runtime can be promoted through a separate immutable v0.3.0 release-preparation commit with only version/release documentation changes.

The stable Nexus Mods update should be made only after that acceptance step and should use the stable v0.3.0 GitHub release artifact rather than an RC package.