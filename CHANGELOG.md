# Changelog

## Unreleased

- Bundle the retail-tested official x64 Ultimate ASI Loader with generated ASI release packages for a complete fresh install.
- Pin the upstream loader release/version, source commit and archive SHA-256; fail release packaging if provenance or x64 validation does not match.
- Include loader provenance and its upstream MIT license in the ASI ZIP while preserving the existing-loader coexistence guidance.

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
- Preserves normal dialogue subtitles and active NPC overhead subtitles across the vanilla-owned pause transition.
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
