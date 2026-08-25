# Design

This document describes the **current production architecture**. Historical experiments and rejected alternatives are documented separately in [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) and the historical files listed in [README.md](README.md).

## Product contract

KCD2 Clean Pause intentionally provides:

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  sharp retained frame, no pause DoF blur
  visible dialogue subtitles remain visible
  active NPC overhead subtitles remain visible
  Escape / Xbox Start -> VanillaMenu
  Xbox B               -> VanillaMenu
```

`VanillaMenu` is KCD2's real pause menu. Clean Pause draws no replacement overlay.

## Principle: KCD2 owns pause

The mod does not manufacture a pause state. KCD2's normal pause already owns the coupled state required for a correct pause: simulation, audio, dialogue/cutscene progression, menu state, and resume behavior.

The implementation therefore:

1. forwards the physical Escape/Start event to vanilla KCD2;
2. independently verifies the pause lifecycle via `Menu@0::IsVisible()`;
3. leaves `Menu@0` logically visible;
4. suppresses only `Menu@0::Render()` while Clean Pause is active.

This preserves a vanilla-owned pause while removing only the menu surface from the retained frame.

## HUD and dialogue-subtitle presentation

KCD2's pause can leave the root `hud@0` element visible while disabling its child clips. Reverse engineering and retail testing identified the relevant layer as 28 named HUD movie clips managed by KCD2's HUD mask.

Before forwarding the pause input the mod captures the current child-visibility booleans. After KCD2 opens its real pause it captures a second vanilla-pause snapshot, then restores the gameplay snapshot for Clean Pause.

During the short transition window `hud@0::Update(float)` may reapply the gameplay snapshot on the validated main thread. `Menu@0::Render()` never mutates HUD state.

When Clean Pause presentation is relinquished, the captured vanilla-pause snapshot is restored before the ordinary menu is shown.

### Movie-clip ownership

`IUIElement::GetMovieClip()` results are treated as borrowed, call-local handles:

- never stored in snapshot/global state;
- never retained across frames;
- never `Release()`d by the mod.

Snapshots contain booleans only.

### Dialogue-subtitle lifetime

The named HUD `CallFunction` hook suppresses exactly two functions while Clean Pause owns presentation:

- `ClearSubtitles`;
- `HideNarrativeSubtitles`.

All other HUD Flash calls are forwarded unchanged.

## NPC overhead subtitles

The root `Bubbles` HUD clip is not the complete state of NPC overhead chatter. KCD2's `C_UIHudBubbles` owns individual bubble IDs and Flash objects, which vanilla pause can update or release even when the root HUD clip is restored.

The `0.2.0` feature line therefore preserves existing bubble objects rather than reconstructing their text or anchors:

1. the runtime discovers `C_UIHudBubbles` from the live `hud@0` event-listener storage using MSVC RTTI;
2. discovery uses no storefront-specific `WHGame.dll` RVA;
3. the bubble freeze is armed before vanilla `Menu@0::SetVisible(true)` executes;
4. only `I_UIHudBubbles::UpdateBubbles()` and `ReleaseBubble()` are suppressed while the vanilla menu is logically open;
5. the freeze is removed after `Menu@0::SetVisible(false)` returns so KCD2 immediately regains normal ownership.

Bubble discovery is optional/fail-open. If the concrete listener layout cannot be validated, the core Clean Pause path continues unchanged; only overhead-bubble preservation may be unavailable.

## Blur-free presentation

The `0.2.0` feature line temporarily suppresses the pause depth-of-field presentation while preserving the user's pre-existing graphics state.

On successful Clean Pause entry:

1. the runtime reads `wh_cl_NearDof` and `r_DepthOfField` through CryEngine's Lua `System.GetCVar` API;
2. the exact current values are retained in the Lua runtime;
3. both CVars are set to `0` before Clean Pause render ownership begins.

Before Escape/Start or B reveals the already-open vanilla pause menu, the captured CVar values are restored. Fail-open paths also attempt the same restoration. If the DoF state cannot be captured/changed safely, Clean Pause does not take presentation ownership and the ordinary visible vanilla pause remains the fallback.

This override is never written to configuration and is not a user preference. Blur-free Clean Pause entry is retail-confirmed on Xbox Store KCD2 1.5.6; exact DoF restoration after the visible-menu/gameplay handoff remains an explicit acceptance check before stable `v0.2.0`.

## Input behavior

### Escape / Start while Clean Paused

The mod restores DoF and the vanilla-pause HUD snapshot, stops suppressing Menu rendering, consumes the transition input, and leaves KCD2 continuously paused. The already-open menu becomes visible.

### B while Clean Paused

The mod performs the same presentation transition: restore DoF and vanilla-pause HUD state and reveal the ordinary pause menu. It does **not** replay a captured Start/Escape sequence and does not forward physical B into gameplay/dialogue/cutscene action maps.

The user then resumes using normal vanilla menu controls.

## Fail-open behavior

A visible vanilla pause menu is the safe fallback. If Menu/HUD/DoF state cannot be resolved or verified, the mod must relinquish Clean Pause presentation ownership rather than leave gameplay live with input swallowed.

Any captured DoF override is restored best-effort before presentation is returned to vanilla, and a transient restore failure remains retryable on later input.

Overhead-bubble preservation is deliberately weaker than the core pause contract: bubble-discovery failure must not disable normal Clean Pause behavior.

## ABI boundary

Verified KCD2 1.5.6 interface facts used by production include:

```text
SSystemGlobalEnvironment + 0x98      -> IGame*
SSystemGlobalEnvironment + 0x140     -> IFlashUI*
IInput::PostInputEvent               -> slot 13
IScriptSystem::ExecuteBuffer         -> slot 6
IFlashUI::GetUIElementByInstanceStr  -> slot 18
IUIElement::Update(float)            -> slot 23
IUIElement::Render                   -> slot 24
IUIElement::SetVisible               -> slot 28
IUIElement::IsVisible                -> slot 29
IUIElement::CallFunction(name, ...)  -> slot 69
IUIElement::GetMovieClip(name)       -> slot 71
IFlashVariableObject::GetDisplayInfo -> slot 26
IFlashVariableObject::SetVisible     -> slot 33
Xbox Start/A/B                       -> 516 / 526 / 527
```

These are interface/retail facts, not fixed `WHGame.dll` RVAs copied across storefront builds.

## Rejected designs

See [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) for the evidence ledger. Production does not use custom `PauseGame` ownership, `only_ui` ownership checks, Menu `SetVisible(false)`, root-HUD-only restoration, reconstructed bubble text/anchors, long-lived movieclip pointers, destructive `Release()` on `GetMovieClip()` results, or synthetic B-resume replay.
