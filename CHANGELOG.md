# Changelog

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
