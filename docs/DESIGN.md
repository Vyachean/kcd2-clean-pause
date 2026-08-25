# Design

## Product contract

KCD2 Clean Pause provides:

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  Escape / Xbox Start -> VanillaMenu
  Xbox B               -> VanillaMenu
```

`VanillaMenu` is KCD2's real pause menu. Clean Pause draws no replacement overlay.

Clean Pause presentation is intentionally sharp: the depth-of-field state associated with the paused scene is temporarily disabled only while the vanilla menu surface is hidden. Visible vanilla pause and ordinary gameplay retain the user's original graphics settings.

## Principle: KCD2 owns pause

The mod does not manufacture a pause state. KCD2's normal pause already owns the coupled state required for a correct pause: simulation, audio, dialogue/cutscene progression, menu state, and resume behavior.

The implementation therefore:

1. forwards the physical Escape/Start event to vanilla KCD2;
2. independently verifies the pause lifecycle via `Menu@0::IsVisible()`;
3. leaves `Menu@0` logically visible;
4. suppresses only `Menu@0::Render()` while Clean Pause is active.

This preserves a vanilla-owned pause while removing the menu surface from the current frame.

## HUD/subtitle presentation

KCD2's pause can leave the root `hud@0` element visible while disabling its child clips. Reverse engineering and retail testing identified the relevant layer as 28 named HUD movie clips managed by KCD2's HUD mask.

Before forwarding the pause input the mod captures the current child visibility booleans. After KCD2 opens its real pause it captures a second vanilla-pause snapshot, then restores the gameplay snapshot for Clean Pause.

During the short transition window `hud@0::Update(float)` may reapply the gameplay snapshot on the validated main thread. `Menu@0::Render()` never mutates HUD state.

When Clean Pause is relinquished, the captured vanilla-pause snapshot is restored before the ordinary menu is shown.

### Movie-clip ownership

`IUIElement::GetMovieClip()` results are treated as borrowed, call-local handles:

- never stored in snapshot/global state;
- never retained across frames;
- never `Release()`d by the mod.

Snapshots contain booleans only.

## Subtitle lifetime

The named HUD `CallFunction` hook suppresses exactly two functions while Clean Pause owns presentation:

- `ClearSubtitles`;
- `HideNarrativeSubtitles`.

All other HUD Flash calls are forwarded unchanged.

## Blur / DoF presentation

Clean Pause temporarily owns two existing KCD2 graphics CVars only for the hidden-menu interval:

- `wh_cl_NearDof`;
- `r_DepthOfField`.

On entry the runtime reads and stores the exact current values through the retail Lua `System.GetCVarValue` API, then sets both to `0` through `System.SetCVar`. No configuration file is written and no permanent graphics preference is changed.

The saved values are restored before Clean Pause releases render ownership to the visible vanilla menu. The same restoration is attempted on every fail-open path. If the initial values cannot be captured or the DoF change cannot be applied safely, Clean Pause does not take presentation ownership and the ordinary visible pause menu remains.

A restore failure is treated as retryable process state: later validated input outside Clean Pause retries restoration instead of assuming the graphics state is clean.

## Input behavior

### Escape / Start while Clean Paused

The mod restores the saved DoF values and vanilla-pause HUD snapshot, stops suppressing Menu rendering, consumes the transition input, and leaves KCD2 continuously paused. The already-open menu becomes visible.

### B while Clean Paused

The current product contract intentionally performs the same presentation transition: restore saved DoF and vanilla-pause HUD state and reveal the ordinary pause menu. It does **not** replay a captured Start/Escape sequence and does not forward physical B into gameplay/dialogue/cutscene action maps.

The user then resumes using normal vanilla menu controls.

## Fail-open behavior

A visible vanilla pause menu is the safe fallback. If Menu/HUD/DoF state cannot be resolved or verified, the mod must relinquish Clean Pause presentation ownership rather than leave gameplay live with input swallowed or graphics state silently modified.

## ABI boundary

Verified KCD2 1.5.6 interface facts used by production include:

```text
SSystemGlobalEnvironment + 0x30     -> IScriptSystem*
SSystemGlobalEnvironment + 0x98     -> IGame*
SSystemGlobalEnvironment + 0x140    -> IFlashUI*
IScriptSystem::ExecuteBuffer         -> slot 6
IInput::PostInputEvent              -> slot 13
IFlashUI::GetUIElementByInstanceStr -> slot 18
IUIElement::Update(float)           -> slot 23
IUIElement::Render                  -> slot 24
IUIElement::SetVisible              -> slot 28
IUIElement::IsVisible               -> slot 29
IUIElement::CallFunction(name, ...) -> slot 69
IUIElement::GetMovieClip(name)      -> slot 71
IFlashVariableObject::GetDisplayInfo -> slot 26
IFlashVariableObject::SetVisible    -> slot 33
Xbox Start/A/B                      -> 516 / 526 / 527
```

These are interface/retail facts, not fixed WHGame RVAs copied across storefront builds.

## Rejected designs

See [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) for the evidence ledger. In particular, production does not use custom PauseGame calls, `only_ui` ownership checks, Menu `SetVisible(false)`, root-HUD-only restoration, long-lived movieclip pointers, destructive `Release()` on `GetMovieClip()` results, or synthetic B resume replay.
