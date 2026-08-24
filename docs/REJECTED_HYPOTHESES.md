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

Rejected on Xbox Store KCD2 1.5.6. rc.6 diagnostics showed `only_ui=false` before, immediately after, and well after the visible vanilla pause menu opened. At the same time `Menu@0` resolved and its visibility tracked vanilla pause correctly.

### `Menu@0::IsVisible()` after the mod calls `SetVisible(false)`

Rejected as an ownership architecture. Once the mod changes Menu visibility, `false` cannot distinguish "vanilla pause still active but hidden by us" from "vanilla pause closed".

The accepted model leaves Menu logically visible and suppresses only `Menu@0::Render()`.

### Fixed libKCD2 WHGame RVAs for production runtime lookup

Rejected. Xbox Store retail relative addresses observed in logs do not match the libKCD2 reference build. Fixed WHGame RVAs are storefront/build dependent.

### Writable-section scan for `S_GameContext` / `C_UIMenu`

Rejected after the menu-mode diagnostic prevented normal startup. Aggressive writable-section scanning/validation is too expensive and risky for bootstrap.

## Presentation hypotheses

### Hiding `Menu@0` with `SetVisible(false)`

Superseded by render suppression. It destroys the independent `IsVisible()` lifecycle signal.

### Suppressing only `Menu@0::Render()`

**Accepted foundation, not rejected.** rc7b proved that this keeps vanilla pause ownership alive while hiding the pause menu. World simulation and audio pause, and second Escape/Start can reveal the already-open vanilla menu without an unpause/re-pause transition.

### One-shot `IFlashUI::SetHudElementsVisible(true)` is sufficient

Rejected by rc7c. The call was made after pause acquisition, `hud@0` resolved, and `hud.ClearSubtitles` was actually intercepted, yet the user observed no visible HUD/subtitle difference from rc7b.

### Persistent global HUD gate holding is sufficient

Rejected by rc7d. `IFlashUI::SetHudElementsVisible(false)` was intercepted during pause acquisition/Clean Pause, but the user still saw no HUD.

Do not continue adding stronger global-HUD-gate variants unless new evidence shows the child HUD state is already correct and the root alone is preventing rendering.

### Persistent concrete `hud@0::SetVisible(false)` suppression is sufficient

Rejected by rc7d. The concrete hook was active and `hud@0::IsVisible() == true` was verified on Clean Pause entry, but the user still saw no HUD/hints/subtitles.

### `hud@0::IsVisible() == true` proves HUD presentation is visible

Rejected by rc7d. It is only the root Flash-element visibility flag.

Static libKCD2 analysis explains the discrepancy: `C_UIHudMask` separately controls 28 named child movie clips inside the still-visible `hud` movie according to active UI sources. Vanilla pause can therefore leave `hud@0` visible while disabling relevant children.

### Blocking `hud.ClearSubtitles` alone preserves visible subtitles

Rejected as a complete solution. rc7c proved the call can be intercepted, but no subtitle was visible because the HUD presentation itself remained hidden.

The narrow `ClearSubtitles` / `HideNarrativeSubtitles` suppression remains useful only as a secondary lifetime safeguard after child presentation is preserved.

### Force every HUD child visible during Clean Pause

Rejected **by design**, without retail testing. The product requirement is to preserve the current frame/UI, not to expose normally-hidden widgets, cursors, crime indicators, dialog sides, dice UI, etc.

rc7e must snapshot the pre-pause visibility of all 28 children and replay that exact bool per child.

## Input/resume findings

### Forward physical Xbox B to the hidden vanilla Menu

Rejected by rc7b. While Menu rendering was suppressed, physical B did not directly resume; the user first had to reveal the visible vanilla menu.

Physical B must not leak to gameplay/dialog/cutscene action maps while Clean Pause is active.

### Assume KCD2 XInput `KeyId` values are one contiguous range

Rejected by rc7d retail evidence.

The old enum started at 512 and auto-incremented, compiling:

- `XiStart=516` (accidentally correct);
- `XiA=522` (wrong);
- `XiB=523` (wrong).

The retail log proves:

- `xi_start=516`;
- `xi_a=526`;
- `xi_b=527`.

Only directly evidenced controller ids may be named in the active ABI. Do not infer the gaps.

### Replay the captured vanilla pause key pair for B

**Still unverified, not rejected.** rc7d physically received `xi_b=527`, but the wrong enum meant `key == KeyId::XiB` never matched and the replay function was never entered.

Therefore rc7d says nothing about whether the replay mechanism works. rc7e is the first candidate with a correct B id and can test it without leaking physical B into dialogue/cutscene/gameplay.

## Current accepted foundation

1. KCD2 itself owns pause.
2. Real Escape/Start is forwarded to vanilla KCD2.
3. `Menu@0::IsVisible()` is the retail lifecycle signal while Menu visibility is untouched by the mod.
4. Suppressing `Menu@0::Render()` creates the hidden vanilla pause.
5. World simulation and audio pause correctly.
6. Second Escape/Start can reveal the existing vanilla menu while keeping pause continuous.
7. Strong vanilla pause depth-of-field blur is accepted and out of scope.
8. The missing HUD layer is below `hud@0` root visibility: KCD2's `C_UIHudMask` controls 28 child clips.
9. The next candidate preserves an exact pre-pause child-visibility snapshot through verified Flash interfaces.
10. Direct B resume remains to be proven now that its retail key id is corrected.

All unresolved paths must fail open to ordinary visible vanilla pause behavior.
