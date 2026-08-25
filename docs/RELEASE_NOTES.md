# KCD2 Clean Pause v0.2.0

Stable feature release for **Kingdom Come: Deliverance II 1.5.6** on Windows.

## Highlights since v0.1.0

- Adds `KCD2CleanPause.asi` alongside the standalone `version.dll` build.
- Adds a process-wide duplicate-load guard.
- Removes the vanilla pause DoF blur from Clean Pause while preserving/restoring the user's prior `wh_cl_NearDof` and `r_DepthOfField` values.
- Preserves normal dialogue subtitles across the vanilla-owned pause transition.
- Preserves active NPC speech bubbles / overhead subtitles instead of losing them when vanilla pause updates the bubble system.
- Keeps the accepted input contract: Escape/Start or Xbox B from Clean Pause reveals the already-open vanilla pause menu.

## Support status

### Standalone `version.dll` — supported

The standalone path is retail-proven on the primary Xbox Store / Xbox app KCD2 1.5.6 target. The latest retail observation confirms normal Clean Pause/menu/resume behavior after the NPC overhead-subtitle preservation change.

### ASI edition — experimental

`KCD2CleanPause.asi` is built and packaged from the same runtime, but the ASI loading path and coexistence with another real ASI plugin have not been exercised in retail. It is included for users who need a shared-loader alternative, but it is not yet claimed as a supported edition.

## Packages

- `kcd2-clean-pause-v0.2.0-version-dll.zip` — supported standalone edition.
- `kcd2-clean-pause-v0.2.0-asi.zip` — experimental ASI edition; requires a compatible x64 ASI loader.
- `SHA256SUMS.txt` — checksums for both packages.

Do not intentionally install both Clean Pause editions together.

## Compatibility / safety

Runtime compatibility is currently claimed for KCD2 **1.5.6** only.

The implementation intentionally avoids custom/inferred `PauseGame` ownership, action-map replacement, fixed storefront-specific `WHGame.dll` RVAs, long-lived Flash movieclip pointers, destructive `Release()` calls on borrowed movieclip handles, and synthetic B-resume replay. Failure paths prefer ordinary visible vanilla pause behavior.
