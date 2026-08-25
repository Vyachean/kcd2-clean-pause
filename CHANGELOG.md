# Changelog

## v0.1.1-rc.3 — 2026-08-25

Corrected blur-free presentation prerelease.

- Fixes the rc.2 Lua CVar getter from nonexistent `System.GetCVarValue` to CryEngine's actual `System.GetCVar` API.
- Retail-confirmed on the primary Xbox Store KCD2 1.5.6 target that Xbox Start enters Clean Pause again and the retained frame is sharp with the pause DoF blur removed.
- Keeps exact DoF-state restoration before returning to visible vanilla presentation; that restoration handoff remains to be explicitly observed before stable promotion.
- Retains the dual ASI / standalone `version.dll` packaging and process-wide duplicate-load guard.

## v0.1.1-rc.2 — 2026-08-25

Superseded presentation/safety prerelease. Do not use for testing.

- Attempted blur-free Clean Pause by temporarily disabling `wh_cl_NearDof` and `r_DepthOfField`.
- Used nonexistent Lua API `System.GetCVarValue`, causing the DoF capability path to fail open to the ordinary visible pause menu on retail.
- Added a process-wide guard so accidental simultaneous ASI + `version.dll` installation cannot install duplicate Clean Pause hooks.

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
