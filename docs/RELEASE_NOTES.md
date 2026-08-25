# KCD2 Clean Pause v0.2.0-rc.1

Release candidate for **Kingdom Come: Deliverance II 1.5.6** on Windows.

This is the first prerelease under the normalized SemVer scheme. It consolidates the user-facing feature work that was previously published incrementally as `v0.1.1-rc.1` through `v0.1.1-rc.4`. There is no intentional runtime behavior change relative to `v0.1.1-rc.4`; the version moves to `0.2.0` because the accumulated changes are features, not a patch to `0.1.0`.

## Highlights since v0.1.0

- Adds two mutually exclusive distribution editions built from the same runtime:
  - `KCD2CleanPause.asi` for a shared ASI-loader setup;
  - standalone `version.dll` for self-contained installation.
- Adds a process-wide duplicate-load guard so accidental ASI + standalone installation cannot install the Clean Pause hooks twice.
- Removes the vanilla pause DoF blur from hidden Clean Pause while preserving and restoring the user's prior `wh_cl_NearDof` and `r_DepthOfField` values.
- Preserves normal dialogue subtitles across the vanilla-owned pause transition.
- Preserves active NPC speech bubbles / overhead subtitles in Clean Pause instead of losing them when vanilla pause updates the bubble system.
- Keeps the original product contract: Escape/Start or Xbox B from Clean Pause reveals the already-open vanilla pause menu; direct B resume is not implemented.

## Two installation editions

- `kcd2-clean-pause-v0.2.0-rc.1-asi.zip` — contains `KCD2CleanPause.asi`; requires a compatible x64 ASI loader, normally installed as `dinput8.dll` beside the game executable / `WHGame.dll`.
- `kcd2-clean-pause-v0.2.0-rc.1-version-dll.zip` — contains the standalone `version.dll` proxy; no separate ASI loader is required.

Use the ASI edition when another mod already owns `version.dll` or when a compatible shared ASI loader is already installed. Do **not** intentionally install both Clean Pause editions together.

## Retail acceptance evidence

On the primary Xbox Store / Xbox app KCD2 1.5.6 target:

- the core vanilla-owned Clean Pause lifecycle is retail-proven;
- Xbox Start enters Clean Pause without drawing the normal pause menu;
- the retained frame is sharp with the pause DoF blur removed;
- normal visible subtitle UI is preserved;
- NPC overhead subtitles are preserved and appear together with the restored main HUD.

Before promoting this candidate to stable `v0.2.0`, the remaining useful checks are:

- confirm during normal play that an old overhead line does not remain permanently stuck after KCD2 regains bubble ownership;
- explicitly observe normal DoF after revealing/closing the vanilla pause menu and resuming gameplay;
- complete the ASI retail-equivalence checklist;
- verify coexistence with at least one other real KCD2 ASI plugin using the same loader.

## Compatibility / safety

Runtime compatibility is currently claimed for KCD2 **1.5.6** only.

The implementation intentionally avoids custom/inferred `PauseGame` ownership, action-map replacement, fixed storefront-specific `WHGame.dll` RVAs, long-lived Flash movieclip pointers, destructive `Release()` calls on borrowed movieclip handles, and synthetic B-resume replay. Failure paths prefer ordinary visible vanilla pause behavior.
