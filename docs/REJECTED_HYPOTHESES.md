# Rejected hypotheses and retail evidence

This document records hypotheses that were tested and rejected while developing Clean Pause for Kingdom Come: Deliverance II 1.5.6 Windows retail. A rejected hypothesis must not be reintroduced without new retail evidence that directly invalidates the recorded result.

## Rejected pause ownership mechanisms

### Profile/action routing as the primary pause interception path

Rejected after early rc.1/rc.2 experiments. It could lose or break Escape/Start handling and is not acceptable as the production owner of pause.

Do not use runtime action-map reloads, persistent remapping, profile replacement, or `Player.OnAction` replacement as the primary pause mechanism.

### Inferred native `PauseGame` ABI

Rejected in rc.4. `SSystemGlobalEnvironment + 0x98` is `IGame*`, not `IGameFramework*`. KCD2 `IGame` slot 13 is `GetName()`, returning `"kcd2"`; calling it through a guessed PauseGame-shaped ABI produced a false success signal.

Rule: never infer pause ownership merely because an unknown native call returned without crashing.

### Lua `PauseGame` as the production mechanism

Rejected in rc.5. The route freezes world simulation but does not reproduce the full vanilla pause lifecycle: audio/UI continue and subtitle lifetime is not frozen.

`CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, and inferred direct native PauseGame calls remain forbidden production mechanisms.

## Rejected pause-state signals

### `ActionMapManager.IsFilterEnabled("only_ui")`

Rejected on Xbox Store KCD2 1.5.6. The rc.6 diagnostic showed `only_ui=false` before, immediately after, and well after vanilla pause opened. At the same time `Menu@0` resolved and its visibility tracked the visible vanilla pause menu correctly.

Conclusion: `only_ui` is not a valid vanilla-pause ownership invariant on this retail build.

### `Menu@0::IsVisible()` alone after calling `SetVisible(false)`

Rejected as an architecture even though the locator itself is valid. Once the mod changes the menu's visibility, `false` can no longer distinguish "vanilla pause still active but hidden by us" from "vanilla pause actually closed".

The accepted presentation model therefore leaves Menu logically visible and suppresses only its rendering.

### Fixed libKCD2 runtime RVAs for storefront-independent runtime lookup

Rejected for production. Xbox Store retail relative addresses observed in logs do not match the reverse-engineered libKCD2 RVAs. Fixed WHGame RVAs are storefront/build dependent and must not be used as the production discovery mechanism.

### Writable-section scan for `S_GameContext` / `C_UIMenu`

Rejected after the rc.6 menu-mode diagnostic prevented normal startup. The diagnostic only reached bootstrap and never reached its active state. Aggressive writable-section scanning/validation is too expensive and risky for startup.

## Presentation hypotheses

### Hiding `Menu@0` with `SetVisible(false)`

Superseded by render suppression. It destroys the independent `IsVisible()` lifecycle signal and makes ownership verification ambiguous.

### Suppressing only `Menu@0::Render()`

Partially accepted. rc7b retail testing proved that this produces the desired hidden vanilla pause presentation while retaining a live vanilla pause lifecycle. World simulation and audio pause correctly, and a second Escape/Start can reveal the already-open vanilla menu without an unpause/re-pause transition.

This is the current pause/menu foundation.

### `IFlashUI::SetHudElementsVisible(true)` is sufficient to restore HUD/subtitles during vanilla pause

Rejected by rc7c retail testing. The verified API call was made after vanilla pause acquisition, the `hud@0` hook installed successfully, and `hud.ClearSubtitles` was actually intercepted, yet the user observed no visible HUD/subtitle difference compared with rc7b.

Conclusion: the global HUD visibility gate is not sufficient by itself. Vanilla pause also changes presentation at the concrete HUD element/layer level. The next candidate must hold the actual HUD element visible rather than relying only on the global gate.

### Blocking `hud.ClearSubtitles` alone is sufficient to preserve visible subtitles

Not sufficient by itself. rc7c proved the call can be intercepted, but because the HUD remained hidden the user still saw no subtitle. Keep this narrow protection as a secondary safeguard only after concrete HUD visibility is restored.

## Input/resume findings

### Forward physical Xbox B to the hidden vanilla Menu to resume

Rejected by rc7b retail testing. While Menu rendering is suppressed, physical B did not directly resume; the user had to reveal the visible vanilla menu first.

Physical B must not leak to gameplay/dialog/cutscene action maps while Clean Pause is active.

### Replaying the captured vanilla pause key pair for B

Still unverified. rc7c included this route, but the supplied retail log contains only Escape events while Clean Pause was active and therefore does not contain a B-resume attempt. Do not claim this route works until a retail log records and verifies it.

## Current accepted foundation

The current accepted facts are:

1. KCD2 itself must own pause.
2. A real Escape/Start event is forwarded to vanilla KCD2.
3. `Menu@0::IsVisible()` is a reliable retail lifecycle signal as long as the mod does not mutate Menu visibility.
4. Suppressing only `Menu@0::Render()` creates a real hidden vanilla pause.
5. World simulation and audio pause correctly.
6. Second Escape/Start may reveal the already-open vanilla menu while keeping pause continuous.
7. Strong vanilla pause depth-of-field blur is accepted and out of scope.
8. HUD/subtitle restoration still requires concrete HUD-element visibility control.
9. Direct B resume remains to be proven.

All unresolved paths must fail open to ordinary visible vanilla pause behavior.