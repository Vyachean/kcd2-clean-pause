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
2. observes the validated vanilla `IGameFramework::PauseGame(true, ...)` call as the preferred event barrier; the mod never calls `PauseGame` itself; for the exact pending Clean Pause transition it preserves vanilla `pause`/`force` ownership but clamps only the documented SFX/Voice fade duration to `0 ms`, so dialogue does not continue after the retained frame freezes;
3. accepts presentation ownership immediately after the outer physical press dispatch returns when that barrier was observed, instead of waiting for Start/Escape release;
4. uses `Menu@0::IsVisible()` as the visible-menu/fail-open lifecycle signal when the barrier is unavailable;
5. leaves `Menu@0` logically visible;
6. suppresses only `Menu@0::Render()` while Clean Pause is active.

This preserves a vanilla-owned pause while removing only the menu surface from the retained frame.

## HUD and dialogue-subtitle presentation

KCD2's pause can leave the root `hud@0` element visible while disabling its child clips. Reverse engineering and retail testing identified the relevant layer as 28 named HUD movie clips managed by KCD2's `C_UIHudMask`.

The root `hud@0` visibility is a separate state controlled by `wh_ui_ShowHud`; it is not represented by the 28 `I_UIHudMask` element values. Every HUD presentation snapshot therefore contains both the exact root visibility and the 28 child visibility booleans. Restore never forces the root visible: if the target root is hidden it is hidden before child replay, and if it must become visible the children are restored first and the root is revealed last.

Before forwarding pause input, the mod captures the current Flash visibility of those 28 clips plus root visibility as the gameplay presentation it wants to retain. The no-blink path then treats KCD2's internal `C_UIHudMask` state and Flash presentation as two deliberately separate layers:

1. the concrete `C_UIHudMask` listener is discovered from `hud@0` listener storage by MSVC RTTI, without a storefront-specific `WHGame.dll` RVA;
2. the source-monitor callback and the verified HUD-refresh module message (`id 52`) are observed;
3. vanilla runs first, so KCD2 updates its own authoritative source-derived pause state normally;
4. before the callback returns to rendering, the mod restores only the saved gameplay Flash presentation;
5. the authoritative current vanilla state is read from `I_UIHudMask::IsElementVisible` for all 28 elements, combined with current root `hud@0::IsVisible()`, and retained as a complete fallback snapshot;
6. when Clean Pause presentation is relinquished, the mod reads the current internal mask again and restores that state to Flash before allowing `Menu@0` to render.

The transaction therefore never reconstructs vanilla pause state by taking a whole-HUD Flash snapshot from the middle of an individual mask callback. KCD2 remains the sole owner of logical HUD visibility; Clean Pause temporarily owns only the visible Flash presentation.

`OnModuleMessage` is not treated as a generic visibility mutation: only the verified HUD-refresh message `52` notifies the presentation observer. Source-monitor callbacks remain relevant because they directly update individual mask elements.

MinHook patches shared method bodies rather than one C++ object. The detours are therefore explicitly scoped to the concrete `C_UIHudMask` and source-monitor object identities discovered from the current `hud@0`; callbacks from any other instance are forwarded to vanilla but cannot drive Clean Pause reconciliation. Those identities are published before the mutation observer becomes active.

A transactional Flash replay is allowed only after a fresh complete internal HUD read succeeds. If that fresh read fails after Clean Pause has already pinned gameplay presentation, the previous complete authoritative vanilla snapshot is used for fail-open before ownership is released. If no complete snapshot has ever been captured, the mod still relinquishes presentation rather than continuing with unverifiable state. If replaying the gameplay presentation fails part-way, the just-captured authoritative vanilla snapshot is restored before Menu rendering is released.

### Pending and maintenance behavior

The mask transaction can begin while pause entry is still pending, before `Menu@0` becomes verifiably visible. The preferred completion point is the return from KCD2's own validated `IGameFramework::PauseGame(true, ...)` call during the forwarded physical press. CryEngine documents the third `PauseGame` argument as the SFX/Voice fade-out time; only for this already-validated pending Clean Pause call the detour changes that duration to `0 ms`, while forwarding the original `pause` and `force` values unchanged. This removes the otherwise intentional audio tail after the visual frame has frozen. The detour records the barrier after vanilla returns; Clean Pause presentation is accepted after the outer `PostInputEvent` forwarding returns, avoiding re-entrant Flash/Lua work inside `PauseGame` itself. If no verified barrier is observed, the existing Menu-visibility path remains the compatibility fallback. If the pending attempt expires and no further input arrives, the already-established main-thread `hud@0::Update(float)` path performs rollback to KCD2's vanilla HUD presentation and clears the pending transaction. It does not use update timing to manufacture or retry pause ownership.

Once Clean Pause is active, `hud@0::Update(float)` remains only a short bounded fallback that can reapply the gameplay presentation if required. It honors the same suspension flag used by exit/fail-open handoffs, so it cannot re-pin gameplay HUD while vanilla presentation is being restored.

If `C_UIHudMask` discovery or validation is unavailable before the transaction starts, the earlier Flash snapshot path remains a fail-open compatibility fallback. The transactional path itself never depends on a partially mutated Flash snapshot for vanilla state.

### Movie-clip ownership

`IUIElement::GetMovieClip()` results are treated as borrowed, call-local handles:

- never stored in snapshot/global state;
- never retained across frames;
- never `Release()`d by the mod.

Snapshots contain booleans only (root visibility plus 28 child values).

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
5. because MinHook patches the shared class method body, those two detours suppress calls only when `this` is the exact `I_UIHudBubbles` object discovered from the current `hud@0`; unrelated instances always forward to vanilla;
6. the freeze is removed after `Menu@0::SetVisible(false)` returns so KCD2 immediately regains normal ownership.

Bubble discovery is optional/fail-open. If the concrete listener layout cannot be validated, the core Clean Pause path continues unchanged; only overhead-bubble preservation may be unavailable.

## Blur-free presentation

Clean Pause temporarily suppresses the pause depth-of-field presentation while preserving the user's pre-existing graphics state.

On successful Clean Pause entry:

1. the runtime reads `wh_cl_NearDof` and `r_DepthOfField` through CryEngine's Lua `System.GetCVar` API;
2. the exact current values are retained in the Lua runtime;
3. both CVars are set to `0` before Clean Pause render ownership begins.

Before Escape/Start or B reveals the already-open vanilla pause menu, the captured CVar values are restored. Fail-open paths also attempt the same restoration. If the DoF state cannot be captured/changed safely, Clean Pause does not take presentation ownership and the ordinary visible vanilla pause remains the fallback.

This override is never written to configuration and is not a user preference.

## Input behavior

### Escape / Start while Clean Paused

The mod first suspends every HUD re-pinning path, stops pending transition ownership, restores DoF and KCD2's current vanilla HUD presentation, then stops suppressing Menu rendering. The transition input is consumed and KCD2 remains continuously paused; the already-open menu becomes visible.

### B while Clean Paused

The mod performs the same presentation handoff: suspend HUD pinning, restore DoF and KCD2's current vanilla HUD state, then reveal the ordinary pause menu. It does **not** replay a captured Start/Escape sequence and does not forward physical B into gameplay/dialogue/cutscene action maps.

The user then resumes using normal vanilla menu controls.

## Fail-open behavior

A visible vanilla pause menu is the safe fallback. If Menu/HUD/DoF state cannot be resolved or verified, the mod must relinquish Clean Pause presentation ownership rather than leave gameplay live with input swallowed.

All presentation handoffs suspend the HUD transaction before restoring vanilla state. The preferred source is live `I_UIHudMask::IsElementVisible` plus root `hud@0::IsVisible()`; an authoritative complete fallback snapshot is retained during verified mask mutations in case a later live read unexpectedly fails. Only when transactional mask discovery was unavailable from the start does the compatibility path use the older Flash-captured vanilla snapshot.

The transactional path is fail-closed with respect to presentation ownership: it never keeps gameplay HUD pinned when a fresh authoritative internal read required for reconciliation fails, and it never releases Menu rendering after a partial gameplay replay without first attempting to restore the authoritative vanilla snapshot. Terminal entry failures clear their snapshots so the pending attempt is not silently re-armed.

Any captured DoF override is restored best-effort before presentation is returned to vanilla, and a transient restore failure remains retryable on later input.

Overhead-bubble preservation is deliberately weaker than the core pause contract: bubble-discovery failure must not disable normal Clean Pause behavior.

## Runtime identity and compatibility evidence

Native builds embed the repository `VERSION` and configured short Git commit id in the runtime log. They also log the loaded `WHGame.dll` PE `TimeDateStamp`, `SizeOfImage`, and `CheckSum`. Retail evidence can therefore be tied to a specific mod binary and can establish a concrete KCD2 1.5.6 executable fingerprint for a future strict compatibility gate.

The current runtime still relies on validated KCD2 1.5.6 ABI/layout facts rather than an enforced executable fingerprint. Until a retail fingerprint has been captured and promoted into a gate, compatibility with later game builds must not be assumed.

## ABI boundary

Verified KCD2 1.5.6 interface facts used by production include:

```text
SSystemGlobalEnvironment + 0x98      -> IGame*
SSystemGlobalEnvironment + 0x140     -> IFlashUI*
IGame::Get framework/root accessor   -> slot 16
IGameFramework::PauseGame            -> slot 13 (vanilla owner; pending Clean Pause audio fade -> 0 ms)
IGameFramework::GetISystem           -> slot 19 (identity proof)
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
C_UIHudMask listener subobject       -> +0x10
I_UIHudMask subobject                -> +0x58
C_UIHudMask source monitor           -> +0x60
I_UIHudMask::IsElementVisible        -> slot 1
Xbox Start/A/B                       -> 516 / 526 / 527
```

These are interface/layout facts verified for KCD2 1.5.6, not fixed `WHGame.dll` function/global RVAs copied across storefront builds.

## Third-party runtime dependency

Both native editions statically link MinHook v1.3.4. The dependency is pinned to immutable commit `c3fcafdc10146beb5919319d0683e44e3c30d537`. Binary packages include `THIRD_PARTY_NOTICES.txt` containing the MinHook/HDE redistribution notices required by the upstream license.

## Rejected designs

See [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) for the evidence ledger. Production does not use custom `PauseGame` ownership or synthesized `PauseGame` calls, `only_ui` ownership checks, Menu `SetVisible(false)`, root-HUD-only restoration, reconstructed bubble text/anchors, long-lived movieclip pointers, destructive `Release()` on `GetMovieClip()` results, synthetic B-resume replay, or whole-HUD vanilla Flash snapshots taken from partial `C_UIHudMask` mutation callbacks.
