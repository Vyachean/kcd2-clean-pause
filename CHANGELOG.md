# Changelog

## v0.1.1-rc.3 — 2026-08-25

Retail correction for the blur-free presentation candidate.

- Fixes the Lua CVar getter from the nonexistent `System.GetCVarValue` call used by rc.2 to CryEngine's actual `System.GetCVar` API.
- Keeps the rc.2 DoF design unchanged: save `wh_cl_NearDof` and `r_DepthOfField`, disable them only during Clean Pause, then restore the exact saved values before visible vanilla presentation.
- rc.2 should not be used for testing: its invalid getter forced the DoF path to fail open to the ordinary visible pause menu.

## v0.1.1-rc.2 — 2026-08-25

Presentation/safety prerelease on top of the dual-package model.

- Makes Clean Pause presentation blur-free by temporarily disabling `wh_cl_NearDof` and `r_DepthOfField` only while the vanilla pause-menu surface is hidden.
- Saves and restores the exact pre-Clean-Pause DoF values before returning to the visible vanilla pause menu or any fail-open path.
- Refuses Clean Pause ownership if the DoF state cannot be captured/changed safely.
- Adds retryable restoration if a transient Lua/CVar failure prevents immediate graphics restoration.
- Adds a process-wide guard so accidental simultaneous ASI + `version.dll` installation cannot install duplicate Clean Pause hooks.
- Keeps KCD2 as the sole pause owner; input, subtitle-preservation, and B-to-visible-menu behavior are unchanged.
- Keeps both ASI and standalone `version.dll` release editions.

## v0.1.1-rc.1 — 2026-08-25

Dual-package prerelease.

- Adds `KCD2CleanPause.asi`, loaded by a compatible shared ASI loader.
- Retains the standalone `version.dll` edition for self-contained installation.
- Builds both editions from the same retail-proven Clean Pause runtime; only bootstrap/loading differs.
- Publishes separate `-asi.zip` and `-version-dll.zip` assets with edition-specific installation instructions and shared checksums.
- Adds CI contract coverage for both native images and exact package contents.
- Keeps the ASI edition prerelease-only until its dedicated Xbox Store 1.5.6 retail-equivalence acceptance passes.

## v0.1.0 — 2026-08-24

Initial stable release.

- Uses KCD2's own pause lifecycle rather than a custom PauseGame implementation.
- Hides only the vanilla pause-menu render surface during Clean Pause.
- Preserves gameplay HUD child visibility, including tested subtitle presentation.
- Escape/Start reveals the existing vanilla pause menu.
- Xbox B from Clean Pause also reveals the vanilla pause menu; direct B resume is deferred.
- Removes experimental action-map, `only_ui`, Menu-visibility, synthetic B-replay, long-lived movieclip-pointer, and destructive movieclip-Release approaches from production.
- Targeted and retail-tested against KCD2 1.5.6, primarily the PC Xbox Store / Xbox app build.
