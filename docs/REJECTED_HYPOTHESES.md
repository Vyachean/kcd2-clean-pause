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

Accepted as the current pause/menu foundation. rc7b proved that this keeps vanilla pause ownership alive while hiding the pause menu. World simulation and audio pause, and second Escape/Start can reveal the already-open vanilla menu without an unpause/re-pause transition.

### One-shot `IFlashUI::SetHudElementsVisible(true)` is sufficient

Rejected by rc7c. The verified call was made after pause acquisition, `hud@0` resolved, the HUD CallFunction hook installed, and `hud.ClearSubtitles` was actually intercepted, yet the user observed no visible HUD/subtitle difference from rc7b.

Important distinction: this rejection applies to a **one-shot enable call as the complete solution**. It does not prove that the global gate is irrelevant. Vanilla may set the gate false again during/after pause acquisition. rc7d therefore tests persistent suppression of `SetHudElementsVisible(false)` together with concrete `hud@0` visibility holding. That combined mechanism is currently unverified, not rejected.

### Blocking `hud.ClearSubtitles` alone preserves subtitles

Rejected as a complete solution. rc7c proved the call can be intercepted, but no subtitle was visible because the HUD presentation itself remained hidden. Keep this as a secondary lifetime safeguard only.

### Concrete `hud@0::SetVisible(false)` suppression

Unverified active hypothesis in rc7d. The hook is object-identity gated and false-only. It is combined with persistent global HUD-gate holding to avoid spending separate retail launches on two closely related presentation hypotheses.

## Input/resume findings

### Forward physical Xbox B to the hidden vanilla Menu

Rejected by rc7b. While Menu rendering was suppressed, physical B did not directly resume; the user first had to reveal the visible vanilla menu.

Physical B must not leak to gameplay/dialog/cutscene action maps while Clean Pause is active.

### Replay the captured vanilla pause key pair for B

Still unverified. rc7c contained this route, but the supplied retail log contains Escape interactions only and no physical B attempt. Do not claim it works until a retail log records a B-resume attempt and `Menu@0` closes without menu flash/cancel/skip.

## Current accepted foundation

1. KCD2 itself owns pause.
2. Real Escape/Start is forwarded to vanilla KCD2.
3. `Menu@0::IsVisible()` is the retail lifecycle signal while Menu visibility is untouched by the mod.
4. Suppressing `Menu@0::Render()` creates the hidden vanilla pause.
5. World simulation and audio pause correctly.
6. Second Escape/Start can reveal the existing vanilla menu while keeping pause continuous.
7. Strong vanilla pause depth-of-field blur is accepted and out of scope.
8. HUD/subtitle presentation requires more than the rejected rc7c one-shot global-gate call.
9. Direct B resume remains to be proven.

All unresolved paths must fail open to ordinary visible vanilla pause behavior.
