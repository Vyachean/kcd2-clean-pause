# Changelog

## Unreleased

## v0.3.0-rc.3 — 2026-09-01

Third release candidate for Steam 1.5.6 compatibility.

- Fixes the profiled Steam bootstrap's incorrect assumption that `IGame` vtable slot 16 returns `IGameFramework`.
- Uses the documented Steam 1.5.6 `CCryAction` / `IGameFramework` singleton storage at RVA `0x0549D328`, with exact framework-vtable and `GetISystem() == gEnv->pSystem` validation before installing the optional `PauseGame` observer.
- Restores the mature runtime capability boundary: failure to resolve the optional `PauseGame` barrier no longer blocks the `PostInputEvent` hook or Menu-visible Clean Pause fallback.
- Keeps `IGame[16]` framework discovery isolated to the already runtime-tested Xbox / Microsoft Store 1.5.6 path instead of treating it as a storefront-independent ABI fact.
- Prevents GOG/Epic profiles from falling back to the invalid Steam-style `IGame[16] -> IGameFramework` assumption; their input/Menu fallback remains available while a canonical framework locator is not registered.
- Adds contract tests that make exact-profile readiness independent from framework discovery and pin the Steam `CCryAction` singleton evidence.

The root cause was identified by comparing Clean Pause with working libKCD2/KCSE native mods: those mods use `CCryAction::GetInstance()` for framework functionality, while detailed Steam 1.5.6 RE identifies `IGame[16]` as a different engine-root object.

## v0.3.0-rc.2 — 2026-09-01

Second release candidate for multi-store KCD2 1.5.6 compatibility.

- Keeps exact-profile Steam/GOG/Epic runtime readiness alive for the process lifetime instead of permanently disabling Clean Pause after the previous 120-second startup window.
- Retains the then-current build, ABI, thread-owner, game-name, framework-vtable, and `IGameFramework -> ISystem` safety gates before hooks.
- Polls exact-profile readiness at 100 ms during the initial startup window and backs off to 1 second afterward, avoiding a permanent false-negative without busy-waiting.
- Adds stage-specific readiness diagnostics with observed environment/interface pointers and a 30-second heartbeat while a supported build is still waiting.
- Preserves the already runtime-tested Xbox / Microsoft Store bounded legacy discovery path unchanged.
- Responds to the v0.3.0-rc.1 Steam smoke test, which correctly matched the Steam fingerprint/profile and canonical `gEnv` and no longer crashed, but timed out before hooks were installed.

RC2 fixed the premature readiness deadline but did not correct the underlying Steam framework-identity assumption; RC3 supersedes it for Steam acceptance testing.

## v0.3.0-rc.1 — 2026-08-31

Release candidate for multi-store KCD2 1.5.6 compatibility.

- Adds fail-closed runtime profiles for all four known PC storefronts: Steam, GOG, Epic Games Store, and Xbox / Microsoft Store.
- Separates storefront metadata, shipped-build identity, ABI, and environment-locator strategy so one ASI can support different store binaries without treating storefront as ABI.
- Fixes the Steam v0.2.2 failure where the legacy writable-memory `gEnv` scan could accept a false-positive runtime object and then observe invalid framework/input/UI state.
- Uses exact distribution-specific canonical `gEnv` evidence for Steam/GOG/Epic, with an additional one-time code-anchor cross-check on the captured Steam build.
- Keeps the already runtime-tested Xbox / Microsoft Store 1.5.6 discovery path behind its exact PE fingerprint and stronger live identity checks.
- Requires the resolved main-thread ID to belong to the current process and verifies the then-assumed `IGame -> IGameFramework -> ISystem` identity before installing version-specific hooks.
- Rejects unknown/mismatched builds and unsupported future ABIs before hook installation.
- Adds executable Windows tests for storefront/build matching, exact environment resolution, fail-closed behavior, and real `whdlversions.json` path/parsing fixtures.
- Fixes shared ASI-loader installation guidance so plugin placement follows the loader's actual search path.
- Removes superseded Lua/profile prototype implementation, builders, fixtures, and retail-profile source data from the current production tree.
- Moves historical research and retail evidence under `docs/history/` so `native/` is unambiguously the supported runtime implementation.
- Publishes only the ASI package; new standalone `version.dll` publication remains withheld while Defender investigation #38 is unresolved.

This candidate is intended for focused Steam smoke QA before promoting the same runtime to stable v0.3.0. GOG/Epic profiles are backed by public reverse-engineering and external runtime evidence but are not yet claimed as Clean Pause runtime-tested by this project.

## v0.2.2 — 2026-08-27

Packaging release for the supported ASI edition.

- Bundles the retail-tested official x64 Ultimate ASI Loader with the generated ASI release package for a complete fresh installation.
- Pins upstream Ultimate ASI Loader v9.7.4, its source commit, release asset, and SHA-256 instead of using a floating latest download.
- Fails release packaging if the upstream archive digest or x64 loader validation does not match the reviewed input.
- Includes loader provenance and the upstream MIT license in the ASI ZIP.
- Preserves the existing-loader path: users who already have a compatible `dinput8.dll` can keep it and install only `KCD2CleanPause.asi`.
- Does not change the Clean Pause runtime behavior accepted in v0.2.1.

## v0.2.1 — 2026-08-26

Patch release for the retail-accepted no-blink Clean Pause transition on KCD2 1.5.6.

- Prevents KCD2's pause HUD-mask transition from rendering an intermediate hidden-HUD frame before Clean Pause presentation is established.
- Narrows HUD/subtitle presentation pinning to the actual validated vanilla `PauseGame` transition instead of the whole Start press/release correlation window, eliminating the pre-pause visual stall while keeping dialogue/audio pause synchronized with the retained frame.
- Uses KCD2's authoritative `C_UIHudMask` state for vanilla-menu handoff while keeping KCD2 as the sole logical pause/HUD owner.
- Scopes globally patched HUD-mask and NPC-bubble method hooks to the exact runtime objects discovered from the current `hud@0` instance.
- Preserves the root `hud@0` visibility state exactly, including configurations where `wh_ui_ShowHud` disables the whole HUD.
- Strengthens transactional fail-open behavior so an internal-state read failure restores the last complete vanilla HUD state instead of exposing a mixed presentation.
- Adds runtime `VERSION`, Git build id, and `WHGame.dll` PE fingerprint logging so retail evidence can be tied to a specific binary and future game-version compatibility gates.
- Pins MinHook v1.3.4 to its immutable commit and includes the required MinHook/HDE redistribution notice in binary packages.
- Expands validation to verify the complete 17-export standalone `version.dll` proxy surface.
- Promotes the ASI loading path used with the upstream Ultimate ASI Loader to the supported v0.2.1 distribution after retail acceptance.
- Withholds the v0.2.1 standalone `version.dll` asset while Microsoft Defender issue #38 remains unresolved; the standalone target continues to build and validate in CI but is not publicly distributed by this release.

## v0.2.0 — 2026-08-25

Stable feature release for the retail-proven standalone Clean Pause path.

- Consolidates the feature work previously published incrementally as `v0.1.1-rc.1` through `v0.1.1-rc.4`.
- Adds dual ASI / standalone `version.dll` distribution built from the same Clean Pause runtime.
- Adds process-wide duplicate-load protection.
- Keeps Clean Pause sharp by temporarily removing pause DoF blur and restoring the prior graphics state before normal vanilla presentation resumes.
- Preserves normal dialogue subtitles and active NPC overhead subtitles across the vanilla pause transition.
- Keeps the accepted Start/Escape/B behavior and fail-open vanilla pause contract.
- Marks the standalone `version.dll` edition supported after retail acceptance of normal pause/menu/resume behavior.
- Keeps the ASI edition experimental until its loading path receives direct retail testing.

The old `v0.1.1-rc.1` through `v0.1.1-rc.4` tags remain immutable historical prereleases. No stable `v0.1.1` is planned.

## v0.1.1-rc.4 — 2026-08-25

Historical prerelease from before versioning normalization.

- Preserves active NPC speech bubbles / overhead subtitles across the vanilla pause transition instead of restoring only the root `Bubbles` HUD clip.
- Discovers KCD2's `C_UIHudBubbles` runtime object through the `hud@0` listener list and MSVC RTTI; no fixed `WHGame.dll` RVA is introduced.
- Freezes only `I_UIHudBubbles::UpdateBubbles()` and `ReleaseBubble()` while `Menu@0` is logically visible, arming before vanilla `SetVisible(true)` and releasing after `SetVisible(false)` returns.
- Keeps the bubble hook optional/fail-open so an unsupported listener layout cannot disable the proven Clean Pause path.
- Retains blur-free presentation, exact DoF restoration, dual ASI / standalone packaging, and duplicate-load protection.

## v0.1.1-rc.3 — 2026-08-25

Historical prerelease from before versioning normalization.

- Fixes the rc.2 Lua CVar getter from nonexistent `System.GetCVarValue` to CryEngine's actual `System.GetCVar` API.
- Retail-confirmed on the primary Xbox Store KCD2 1.5.6 target that Xbox Start enters Clean Pause again and the retained frame is sharp with the pause DoF blur removed.

## v0.1.1-rc.2 — 2026-08-25

Superseded historical prerelease. Do not use for testing.

- Attempted blur-free Clean Pause by temporarily disabling `wh_cl_NearDof` and `r_DepthOfField`.
- Used nonexistent Lua API `System.GetCVarValue`, causing the DoF capability path to fail open to the ordinary visible pause menu on retail.
- Added a process-wide guard so accidental simultaneous ASI + `version.dll` installation cannot install duplicate Clean Pause hooks.

## v0.1.1-rc.1 — 2026-08-25

Historical prerelease from before versioning normalization.

- Adds `KCD2CleanPause.asi`, loaded by a compatible shared ASI loader.
- Retains the standalone `version.dll` edition for self-contained installation.
- Builds both editions from the same runtime; only bootstrap/loading differs.

## v0.1.0 — 2026-08-24

Initial stable release.

- Uses KCD2's own pause lifecycle rather than a custom PauseGame implementation.
- Hides only the vanilla pause-menu render surface during Clean Pause.
- Preserves gameplay HUD child visibility, including tested subtitle presentation.
- Escape/Start reveals the existing vanilla pause menu.
- Xbox B from Clean Pause also reveals the vanilla pause menu; direct B resume is deferred.
- Removes experimental action-map, `only_ui`, Menu-visibility, synthetic B-replay, long-lived movieclip-pointer, and destructive movieclip-Release approaches from production.
- Targeted and retail-tested against KCD2 1.5.6, primarily the PC Xbox Store / Xbox app build.
