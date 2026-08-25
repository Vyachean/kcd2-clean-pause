# Rejected hypotheses and retail evidence

A rejected path must not be reintroduced without new direct retail evidence.

This file is an engineering evidence ledger. For the active architecture, see [DESIGN.md](DESIGN.md).

## Pause ownership

Rejected:

- profile/action routing as the primary pause interception path;
- runtime action-map reload/remapping or `Player.OnAction` replacement;
- calling an inferred/native `PauseGame` as a custom pause owner;
- `CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, or Lua/custom `PauseGame` as production owner;
- `ActionMapManager.IsFilterEnabled("only_ui")` as vanilla-pause ownership evidence;
- `Menu@0::SetVisible(false)` as the hidden-pause ownership architecture;
- fixed libKCD2 `WHGame.dll` RVAs for storefront-independent runtime lookup;
- aggressive writable-section `S_GameContext` / `C_UIMenu` scanning.

Accepted foundation:

- KCD2 owns pause;
- real Escape/Start is forwarded;
- the verified vanilla `IGameFramework::PauseGame(true, ...)` return may be observed as an event barrier, but is never called by the mod;
- `Menu@0::IsVisible()` remains the visible-menu/fail-open lifecycle signal;
- Menu visibility is untouched;
- only `Menu@0::Render()` is suppressed during Clean Pause.

## HUD presentation

Rejected:

- one-shot global HUD visibility restore;
- persistent global HUD gate holding;
- persistent root `hud@0::SetVisible(false)` suppression;
- `hud@0::IsVisible()==true` as proof that gameplay child HUD is visible;
- `ClearSubtitles` suppression alone as complete subtitle restoration;
- forcing all HUD children visible.

Accepted retail finding:

- KCD2's 28 child HUD movie clips are the relevant main-HUD presentation layer;
- current dialogue subtitles can remain visible during Clean Pause when their child state and lifetime are preserved.

## NPC overhead subtitles

Rejected:

- treating the root `Bubbles` HUD clip as the complete overhead-subtitle state;
- reconstructing bubble text, speaker identity, or screen/world anchors after vanilla has already released the underlying bubble object.

Accepted approach:

- discover the live `C_UIHudBubbles` listener through the `hud@0` listener storage and MSVC RTTI;
- freeze only `UpdateBubbles()` and `ReleaseBubble()` while the vanilla menu is logically open;
- keep discovery optional/fail-open so a bubble-layout mismatch cannot disable core Clean Pause behavior.

## Movieclip pointer ownership

### Persist raw `IUIElement::GetMovieClip()` pointers across frames

Rejected after historical retail testing. It visibly restored subtitles but introduced stale/cross-thread pointer lifetime risk and was followed by a crash after returning to the visible menu.

Permanent rule: snapshots store visibility booleans, never movieclip pointers.

### Call `Release()` on `IUIElement::GetMovieClip()` results

Rejected by historical retail evidence. A candidate completed the 28-child gameplay snapshot, then crashed during the following pause transition. `IFlashVariableObject::Release()` is destructive and caller ownership is not established for `IUIElement::GetMovieClip()` results.

Permanent active rule:

- treat `GetMovieClip()` results as borrowed/cached;
- use them only within the current helper call;
- do not retain them;
- do not `Release()` them.

## Render/update lifecycle

Rejected:

- HUD child acquisition/mutation/release from `Menu@0::Render()`.

`Menu::Render()` is presentation-only. Bounded child-state maintenance belongs to verified `hud@0::Update(float)` on the validated main thread.

## Input findings

Rejected:

- forwarding physical Xbox B directly to invisible UI/gameplay as a resume solution;
- assuming KCD2 XInput IDs form a contiguous range.

Retail-proven IDs:

- Start = 516;
- A = 526;
- B = 527.

### Synthetic captured-pause-key replay for direct B resume

This historical experiment never achieved a retail-proven direct resume. The accepted behavior is `B -> visible vanilla pause menu`.

Production therefore contains no synthetic pause-key replay templates/function. A future direct-resume design should use a newly proven, narrower vanilla close/resume mechanism rather than restoring the old experiment.

## Blur handling

Rejected:

- persisting a user graphics-setting change to remove pause blur;
- assuming a fixed previous DoF value instead of capturing the current value;
- using the nonexistent Lua getter `System.GetCVarValue`.

Accepted approach:

- read the current `wh_cl_NearDof` and `r_DepthOfField` through `System.GetCVar`;
- set both to `0` only while Clean Pause owns hidden-menu presentation;
- restore the exact captured values before visible vanilla presentation resumes;
- fail open to the visible vanilla menu if the core DoF capability cannot be used safely.

## Current accepted model

1. KCD2 is the only pause owner.
2. `Menu@0::IsVisible()` proves the pause lifecycle.
3. `Menu@0::Render()` suppression removes only the visible pause menu.
4. Gameplay and vanilla-pause HUD child visibility are stored as separate bool snapshots.
5. `GetMovieClip()` handles are call-local borrowed pointers only.
6. Clean Pause restores gameplay child visibility and narrowly protects normal subtitle lifetime.
7. Active NPC overhead subtitles are preserved by freezing the live bubble update/release lifecycle, not by reconstructing bubbles.
8. The `0.2.0` feature line temporarily removes pause DoF blur and restores the exact captured graphics state before returning presentation to vanilla.
9. Escape/Start or B restores vanilla-pause presentation and reveals the normal menu.
10. Any unresolved core state fails open to ordinary visible vanilla pause behavior.
