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

The mod does not manufacture a pause state. KCD2's normal pause already owns the coupled state required for a correct pause: simulation, audio, dialogue/cutscene progression, menu state and resume behavior.

The shared runtime therefore:

1. forwards the physical Escape/Start event to vanilla KCD2;
2. observes a validated vanilla `IGameFramework::PauseGame(true, ...)` call as the preferred event barrier when that optional capability is available;
3. never calls `PauseGame` itself and forwards the original arguments unchanged;
4. arms HUD/subtitle transition pinning only while the verified vanilla `PauseGame(true)` call is actually executing, not merely while input correlation is pending;
5. accepts presentation ownership after the outer vanilla `PostInputEvent` dispatch returns when the barrier was observed, avoiding re-entrant Flash/Lua work inside `PauseGame`;
6. uses `Menu@0::IsVisible()` as the compatibility/fail-open lifecycle signal when the optional barrier is unavailable;
7. leaves `Menu@0` logically visible and suppresses only its render surface while Clean Pause owns presentation.

This preserves a vanilla-owned pause while replacing only the visible pause presentation.

## Runtime adapters versus shared Clean Pause core

Storefront-specific evidence is isolated from the Clean Pause behavior as far as the current compatibility layer permits.

All supported release_1_5 profiles converge on the same mature input/HUD/Menu/subtitle/bubble/blur implementation after runtime installation. The adapter layer is responsible for proving which shipped binary is running and how to reach build-specific engine roots.

### Xbox / Microsoft Store 1.5.6

The runtime-tested Xbox path keeps its captured legacy environment scan and the separately proven `IGame[16] -> IGameFramework` lookup. That slot-16 interpretation is scoped to this Xbox adapter and is not a universal release_1_5 assumption.

### Steam 1.5.6 `release_1_5-15693`

Steam uses:

- exact PE fingerprint `0x6a350e20 / 0x05b2d000 / 0`;
- canonical `gEnv` RVA `0x0492D7F8` plus an independent one-time `exec autoexec.cfg -> pConsole` anchor cross-check;
- the canonical `CCryAction` framework singleton at storage RVA `0x0549D328`, with expected vtable RVA `0x040472D0` and `GetISystem() == gEnv->pSystem` identity proof;
- lazy acquisition of the optional PauseGame observer on a validated real Pause input so bootstrap timing cannot permanently disable the capability.

Steam `IGame::GetName()` is observed as `"KCD2"`; the captured Xbox runtime returns `"kcd2"`. Those two exact observed spellings are accepted without weakening the remaining build gates.

### GOG / Epic

GOG and Epic use their distribution-specific canonical `gEnv` evidence and the shared core input/Menu path. No canonical framework singleton locator is currently registered for them, and they never fall back to the Xbox slot-16 assumption.

## HUD and dialogue-subtitle presentation

KCD2's pause can keep the root `hud@0` element separate from the visibility of its 28 child HUD elements. The child state is owned by KCD2's `C_UIHudMask`; root visibility is a distinct `hud@0::IsVisible()` state.

Every gameplay/vanilla HUD snapshot therefore contains:

- exact root `hud@0` visibility;
- 28 child visibility booleans;
- no borrowed movieclip pointers.

Restore never blindly forces the root visible: if the target root is hidden it is hidden before child replay, and if it must become visible the children are restored first and the root is revealed last.

### Authoritative fast gameplay snapshot

The concrete `C_UIHudMask` listener is discovered from the current `hud@0` listener storage using MSVC RTTI. Discovery uses class/layout ABI evidence rather than a storefront-specific object RVA.

Once the mask transaction has been validated, its `I_UIHudMask::IsElementVisible` values are the authoritative source for the 28 gameplay child flags. On a physical Pause press, Clean Pause reads those internal flags directly and reads root visibility separately. This is the normal fast path.

The older Scaleform path that walks all 28 named movieclips and calls `GetDisplayInfo` remains only as a compatibility fallback when the internal mask transaction is unavailable. It is no longer the normal pre-pause path.

This change removed the recurring pre-pause main-thread stall seen during Steam acceptance while preserving the same snapshot representation and restore path.

### Transactional pause mutation handling

The no-blink path treats KCD2's logical `C_UIHudMask` state and visible Flash presentation as separate layers:

1. `C_UIHudMask` source-monitor callbacks and the verified HUD-refresh module message (`id 52`) are observed;
2. vanilla runs first, so KCD2 updates its own authoritative logical HUD state normally;
3. a fresh complete internal mask snapshot is captured before Clean Pause changes presentation;
4. while the verified pause transition / Clean Pause presentation owns the screen, the saved gameplay Flash presentation is replayed;
5. the current vanilla internal state is retained as a complete fail-open snapshot;
6. when presentation ownership is relinquished, live internal mask state is preferred and restored to Flash before Menu rendering is released.

The transaction never tries to reconstruct vanilla state from a whole-HUD Flash snapshot taken in the middle of a partial mask mutation.

MinHook patches shared method bodies rather than one C++ object. Detours are therefore scoped to the concrete `C_UIHudMask`, source-monitor, `hud@0` and related object identities discovered for the current HUD lifetime. Calls for unrelated instances are forwarded to vanilla.

If a fresh authoritative internal read fails once transactional pinning has begun, Clean Pause relinquishes ownership rather than continuing with unverifiable state. If presentation replay fails part-way, the most recent complete vanilla snapshot is restored before Menu rendering is released.

### Root HUD visibility

The 28 mask children do not include root `hud@0` visibility. Root state is captured/restored separately.

The exact Steam acceptance path additionally installs a narrowly scoped root-visibility filter on the already shared `CFlashUIElement::SetVisible` hook. During the verified Steam pause transition / established Clean Pause it prevents vanilla from changing root visibility away from the saved gameplay value. A defensive post-`PauseGame(true)` root correction handles mutations that might bypass that shared setter path.

This root filter is Steam-only evidence-driven behavior; Xbox/GOG/Epic do not inherit it by assumption.

### Steam Menu render handoff

On the exact Steam profile, once the correlated real `PauseGame(true)` call begins and the required presentation identities exist, `Menu@0` render suppression is provisionally armed before vanilla enters the pause call. This covers the handoff while the full gameplay HUD is restored.

That provisional state is not unconditional ownership. If the outer input handoff does not end in an accepted Clean Pause state, the prehide is rolled back immediately so the ordinary vanilla pause menu remains available.

### Pending and maintenance behavior

A physical Pause press captures gameplay presentation and establishes only bounded input correlation. Pending correlation by itself does not replay HUD or freeze subtitles.

The transaction is armed for the real verified vanilla `PauseGame(true)` call. Retail Xbox evidence shows that KCD2 may call `PauseGame(true)` on Start release rather than press, so the barrier may be consumed on either phase.

If no verified barrier is observed, the Menu visibility path remains the compatibility fallback. If a pending attempt expires with no further input, the validated main-thread `hud@0::Update(float)` path rolls presentation back to vanilla and clears the attempt.

Once Clean Pause is active, `hud@0::Update(float)` is only a short bounded maintenance fallback that can reapply the saved presentation during the initial hold interval. It honors the same suspension flag used by exit/fail-open handoffs and cannot re-pin gameplay while vanilla state is being restored.

### Movie-clip ownership

`IUIElement::GetMovieClip()` results are treated as borrowed, call-local handles:

- never stored in snapshot/global state;
- never retained across frames;
- never `Release()`d by the mod.

Snapshots contain booleans only.

### Dialogue-subtitle lifetime

The named HUD `CallFunction` hook suppresses exactly two functions while Clean Pause owns presentation or the verified pause transition is active:

- `ClearSubtitles`;
- `HideNarrativeSubtitles`.

All other HUD Flash calls are forwarded unchanged.

## NPC overhead subtitles

The root `Bubbles` HUD clip is not the complete state of NPC overhead chatter. KCD2's `C_UIHudBubbles` owns individual bubble IDs and Flash objects, which vanilla pause can update or release even when the root HUD clip is restored.

The runtime preserves existing bubble objects rather than reconstructing their text or anchors:

1. `C_UIHudBubbles` is discovered from the live `hud@0` event-listener storage using MSVC RTTI;
2. discovery uses no storefront-specific `WHGame.dll` object RVA;
3. the shared `CFlashUIElement::SetVisible` hook observes the exact current `Menu@0` identity;
4. only `I_UIHudBubbles::UpdateBubbles()` and `ReleaseBubble()` are suppressed while the vanilla menu is logically open;
5. shared-method detours suppress calls only when `this` is the exact discovered bubble interface object; unrelated instances forward unchanged;
6. the freeze ends after the menu closes so KCD2 regains normal ownership.

Bubble discovery is optional/fail-open. Failure cannot disable core Clean Pause behavior.

## Blur-free presentation

Clean Pause temporarily suppresses the pause depth-of-field presentation while preserving the user's pre-existing graphics state.

On successful entry:

1. the runtime reads `wh_cl_NearDof` and `r_DepthOfField` through CryEngine's Lua `System.GetCVar` API;
2. the exact current values are retained in the Lua runtime;
3. both CVars are set to `0`.

Before Escape/Start or B reveals the already-open vanilla pause menu, the captured values are restored. Fail-open paths also attempt restoration. A failed restoration remains retryable on later input.

If the DoF state cannot be captured/changed safely, Clean Pause does not take presentation ownership and the ordinary visible vanilla pause remains the fallback.

This override is never written to configuration and is not a user preference.

## Input behavior

### Visible vanilla pause menu

A visible `Menu@0` owns Escape/Start. The profiled input wrapper checks that state before Clean Pause preparation. Once a physical visible-menu Escape/Start press is forwarded, the whole gesture remains in passthrough through the matching release so key-repeat events cannot become a new Clean Pause request after the menu closes.

### Escape / Start while Clean Paused

The mod first suspends HUD re-pinning, clears pending transition ownership, restores DoF and KCD2's current vanilla HUD presentation, then stops suppressing Menu rendering. The transition input is consumed and KCD2 remains paused; the already-open menu becomes visible.

### B while Clean Paused

The same presentation handoff occurs for Xbox B. Clean Pause does **not** synthesize a Start/Escape replay and does not forward physical B into gameplay/dialogue/cutscene action maps. The ordinary pause menu is revealed and normal vanilla controls resume from there.

## Fail-open behavior

A visible vanilla pause menu is the safe fallback. If Menu/HUD/DoF state cannot be resolved or verified, the mod relinquishes Clean Pause presentation ownership rather than leaving gameplay live with input swallowed.

All presentation handoffs suspend HUD pinning before restoring vanilla state. Live `I_UIHudMask::IsElementVisible` plus root `hud@0::IsVisible()` is the preferred source; a complete authoritative fallback snapshot is retained during verified mask mutations. Only when transactional mask discovery was unavailable from the start does the compatibility path rely on the older Flash-captured vanilla snapshot.

Created MinHook detours are also transactional at installation time: if `MH_CreateHook` succeeds but `MH_EnableHook` fails, the created hook is removed and its trampoline pointer is cleared before the installer returns failure. A failed enable must not leave hidden MinHook state that changes a later retry.

Any captured DoF override is restored best-effort before presentation is returned to vanilla. Overhead-bubble preservation is deliberately weaker than the core pause contract: bubble-discovery failure must not disable normal Clean Pause behavior.

## Runtime identity and compatibility evidence

Native builds embed the repository `VERSION` and configured short Git commit id in the runtime log. They also log the loaded `WHGame.dll` PE `TimeDateStamp`, `SizeOfImage` and `CheckSum`.

Production no longer treats release_1_5 ABI compatibility as sufficient by itself. A core version-specific hook is installed only after a registered `BuildProfile` matches its required shipped-build identity and its selected `AbiProfile` is fully supported.

Current exact captured identities include:

- Steam 1.5.6: `0x6a350e20 / 0x05b2d000 / 0`;
- Xbox / Microsoft Store 1.5.6: `0x6a391f7b / 0x05bf2000 / 0`.

GOG/Epic use storefront build-code identity plus independent canonical `gEnv` evidence as documented in [RUNTIME_COMPATIBILITY.md](RUNTIME_COMPATIBILITY.md).

Unknown or mismatched builds install no version-specific Clean Pause hooks.

## ABI boundary

Verified release_1_5 interface/layout facts consumed by the mature adapter include:

```text
SSystemGlobalEnvironment + 0x30      -> IScriptSystem*
SSystemGlobalEnvironment + 0x48      -> IInput*
SSystemGlobalEnvironment + 0x98      -> IGame*
SSystemGlobalEnvironment + 0xC8      -> ISystem*
SSystemGlobalEnvironment + 0x140     -> IFlashUI*
SSystemGlobalEnvironment + 0x1B0     -> main thread id
IInput::PostInputEvent               -> slot 13
IGame::GetLongName                   -> slot 12
IGame::GetName                       -> slot 13
IGame[16]                            -> Xbox-only proven framework/root accessor; not used as Steam IGameFramework
IGameFramework::PauseGame            -> slot 13
IGameFramework::GetISystem           -> slot 19
IScriptSystem::ExecuteBuffer         -> slot 6
IScriptSystem::GetGlobalAny          -> slot 32
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

These are ABI/layout facts. Absolute engine RVAs are modeled separately in matching build profiles/capability adapters and must not be copied across storefront binaries without evidence.

## Native package and process lifetime

ASI and standalone `version.dll` targets compile the same runtime sources; only their bootstrap/loader entry differs. A process-wide guard prevents both editions from installing duplicate hooks if both are accidentally present.

Installed MinHook detours and discovered engine identities are **process-lifetime state**. `Stop()` marks teardown but does not remove every hook or reset the runtime for reuse. Loader-initiated hot unload/reload is unsupported for both editions. Close KCD2 before replacing or removing the module.

Supporting hot unload in the future would require complete hook disable/removal, presentation/DoF restoration, runtime identity reset and repeat-load regression tests before this contract could change.

## Third-party runtime dependency

Both native editions statically link MinHook v1.3.4. The dependency is pinned to immutable commit `c3fcafdc10146beb5919319d0683e44e3c30d537`. Binary packages include `THIRD_PARTY_NOTICES.txt` containing the MinHook/HDE redistribution notices required by the upstream license.

## Current maintainability debt

`clean_pause_native_profiled.cpp` currently macro-renames the old bootstrap/discovery symbols and textually includes `clean_pause_native.cpp` so the mature accepted Clean Pause core can be reused without invasive movement. This was a deliberate compatibility-preservation choice during storefront acceptance, but it is not the desired final translation-unit structure.

Issue #45 tracks the behavior-preserving refactor to:

- compile production `.cpp` files normally;
- separate build discovery/storefront adapters from core runtime state/hook installation;
- expose the minimum private internal API rather than depending on textual inclusion;
- keep Xbox legacy discovery isolated as an explicit compatibility adapter;
- preserve the same Steam/Xbox runtime contract and smoke coverage.

Common Win32 memory validation, MSVC RTTI and MinHook-install helpers are also candidates for deduplication as part of that refactor. Do not combine this structural cleanup with compatibility or AV/reputation changes unless a concrete defect requires it.

## Rejected designs

See [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) for the evidence ledger. Production does not use custom `PauseGame` ownership or synthesized PauseGame calls, `only_ui` ownership checks, Menu `SetVisible(false)`, root-HUD-only restoration, reconstructed bubble text/anchors, long-lived movieclip pointers, destructive `Release()` on `GetMovieClip()` results, synthetic B-resume replay, or whole-HUD vanilla Flash snapshots taken from partial `C_UIHudMask` mutation callbacks.
