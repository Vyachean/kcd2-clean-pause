# Rejected hypotheses and retail evidence

This document records hypotheses tested and rejected while developing Clean Pause for Kingdom Come: Deliverance II 1.5.6 Windows retail. A rejected hypothesis must not be reintroduced without new retail evidence that directly invalidates the recorded result.

## Rejected pause ownership mechanisms

### Profile/action routing as the primary pause interception path

Rejected after rc.1/rc.2. It could lose or break Escape/Start handling.

Do not use runtime action-map reloads, persistent remapping, profile replacement, or `Player.OnAction` replacement as the primary pause mechanism.

### Inferred native `PauseGame` ABI

Rejected in rc.4. `SSystemGlobalEnvironment + 0x98` is `IGame*`, not `IGameFramework*`. KCD2 `IGame` slot 13 is `GetName()`, returning `"kcd2"`; calling it through a guessed PauseGame-shaped ABI produced a false success signal.

Permanent rule: never infer engine state merely because an unknown call returned without crashing.

### Lua/custom `PauseGame` as production pause

Rejected in rc.5. It freezes world simulation but does not reproduce the full vanilla pause lifecycle: audio/UI continue and subtitle lifetime is not frozen correctly.

`CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, and inferred direct native PauseGame remain forbidden production mechanisms.

## Rejected pause-state signals

### `ActionMapManager.IsFilterEnabled("only_ui")`

Rejected on Xbox Store KCD2 1.5.6. rc.6 diagnostics showed `only_ui=false` before, immediately after, and well after visible vanilla pause opened.

### `Menu@0::IsVisible()` after the mod calls `SetVisible(false)`

Rejected as an ownership architecture. The accepted model leaves Menu logically visible and suppresses only `Menu@0::Render()`.

### Fixed libKCD2 WHGame RVAs for production runtime lookup

Rejected. Xbox Store retail relative addresses do not match the libKCD2 reference build. Fixed WHGame RVAs are storefront/build dependent.

### Writable-section scan for `S_GameContext` / `C_UIMenu`

Rejected after the diagnostic prevented normal startup.

## Presentation findings

### Suppressing only `Menu@0::Render()`

**Accepted foundation.** rc7b proved that this keeps vanilla pause ownership alive while hiding the pause menu. World simulation and audio pause, and second Escape/Start can reveal the already-open vanilla menu without an unpause/re-pause transition.

### Root HUD visibility as the missing presentation layer

Rejected by rc7c/rc7d.

Neither one-shot nor persistent `IFlashUI::SetHudElementsVisible(true/false)` control, nor persistent `hud@0::SetVisible(false)` suppression, restored visible HUD/subtitles. rc7d verified `hud@0::IsVisible()==true` while the user still saw no HUD.

Do not return to stronger root-HUD visibility variants.

### `hud@0::IsVisible()==true` proves child HUD presentation

Rejected by rc7d. libKCD2 explains why: `C_UIHudMask` separately controls 28 named child movie clips inside the still-visible `hud` movie according to active UI sources.

### 28-child HUD visibility layer

**Accepted as retail-relevant, not rejected.** rc7e switched to exact visibility of the 28 child clips and the user confirmed that the subtitle at the bottom became visible during Clean Pause.

The mechanism must preserve captured visibility rather than force all 28 children visible.

### Blocking `hud.ClearSubtitles` alone preserves subtitles

Rejected as a complete solution by rc7c. Keep the narrow `ClearSubtitles` / `HideNarrativeSubtitles` suppression only as a secondary lifetime safeguard after child presentation is preserved.

## RC7e lifecycle mechanisms rejected after crash

### Retain `IFlashVariableObject*` HUD wrappers across frames

Rejected after rc7e.

RC7e stored 28 engine-owned Flash variable wrappers in the snapshot and released them during input transitions. `Menu@0::Render()` could concurrently be restoring through those same wrappers. This creates an unsafe cross-thread lifetime / plausible use-after-free or heap corruption.

The retail crash sequence was:

1. Start -> Clean Pause with subtitle visible;
2. Start -> visible vanilla pause menu;
3. B -> crash.

Without a native crash stack the exact faulting instruction is unknown, but the lifetime design is independently unsafe and release-blocking.

Permanent rule: **no engine-owned `IFlashVariableObject*` may survive beyond the helper call that acquired it.**

### Mutate HUD child Flash state from `Menu@0::Render()`

Rejected after the rc7e code audit.

`Menu::Render()` must be presentation-only. It may suppress or forward Menu rendering, but must not acquire HUD child wrappers, call child `SetVisible`, or release Flash wrappers.

Any periodic child maintenance must occur on a validated main-thread UI/update path.

### Reveal vanilla Menu without restoring its captured child HUD state

Rejected after rc7e.

RC7e restored gameplay child visibility during Clean Pause but on second Start merely stopped maintaining it and freed wrappers. It did not restore the exact child state vanilla pause had established before the override.

The corrected design captures a separate vanilla-pause snapshot before overriding child state and restores it before showing Menu or attempting the B replay route.

## Input/resume findings

### Forward physical Xbox B to hidden vanilla Menu

Rejected by rc7b. Physical B must not leak to gameplay/dialog/cutscene while Clean Pause is active.

### Assume XInput `KeyId` values are contiguous

Rejected by rc7d retail evidence. The retail values are:

- `xi_start=516`;
- `xi_a=526`;
- `xi_b=527`.

Only directly evidenced ids may be named in the active ABI.

### Replay the captured vanilla pause key pair for direct B resume

**Still unverified, not rejected.** The rc7e crash happened after second Start had already revealed the ordinary vanilla menu, then B was pressed there. That does not test the direct Clean-Pause B replay path.

RC7f must restore the captured vanilla-pause HUD snapshot before attempting replay and accept resume only when `Menu@0` closes.

## Current accepted foundation

1. KCD2 itself owns pause.
2. Real Escape/Start is forwarded to vanilla KCD2.
3. `Menu@0::IsVisible()` is the retail lifecycle signal.
4. `Menu@0::Render()` suppression creates hidden vanilla pause.
5. World simulation and audio pause correctly.
6. Second Escape/Start reveals the existing vanilla menu continuously.
7. Strong vanilla pause depth-of-field blur is accepted and out of scope.
8. KCD2's 28 HUD child clips are the retail-proven presentation layer for subtitle restoration.
9. Snapshots must be bool-only; Flash wrappers are call-local.
10. Gameplay and vanilla-pause child states must be captured separately and restored symmetrically.
11. Direct B replay remains to be proven.

All unresolved paths must fail open to ordinary visible vanilla pause behavior.
