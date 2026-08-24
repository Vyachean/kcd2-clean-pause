# Rejected hypotheses and retail evidence

A rejected path must not be reintroduced without new direct retail evidence.

## Pause ownership

Rejected:

- profile/action routing as the primary pause interception path;
- runtime action-map reload/remapping or `Player.OnAction` replacement;
- inferred native `PauseGame` ABI;
- `CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, or Lua/custom PauseGame as production owner;
- `ActionMapManager.IsFilterEnabled("only_ui")` as vanilla-pause ownership evidence;
- `Menu@0::SetVisible(false)` as the hidden-pause ownership architecture;
- fixed libKCD2 WHGame RVAs for storefront-independent runtime lookup;
- aggressive writable-section `S_GameContext` / `C_UIMenu` scanning.

Accepted foundation:

- KCD2 owns pause;
- real Escape/Start is forwarded;
- `Menu@0::IsVisible()` is the retail lifecycle signal;
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

- KCD2's 28 child HUD movie clips are the relevant presentation layer;
- rc7e/rc7g demonstrated a visible current subtitle during Clean Pause.

## Movieclip pointer ownership

### Persist raw `IUIElement::GetMovieClip()` pointers across frames

Rejected after rc7e. It visibly restored subtitles but introduced stale/cross-thread pointer lifetime risk and was followed by a crash after returning to the visible menu.

Permanent rule: snapshots store visibility booleans, never movieclip pointers.

### Call `Release()` on `IUIElement::GetMovieClip()` results

Rejected by rc7f retail evidence. rc7f completed the 28-child gameplay snapshot, then crashed during the following pause transition. `IFlashVariableObject::Release()` is destructive and caller ownership is not established for `IUIElement::GetMovieClip()` results.

Permanent active rule:

- treat `GetMovieClip()` results as borrowed/cached;
- use them only within the current helper call;
- do not retain them;
- do not Release them.

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

This experiment is **not shipped in v0.1.0**. It never achieved a retail-proven direct resume, while the observed safe behavior (`B -> visible vanilla menu`) is acceptable for the initial stable release.

Stable production therefore removes the replay templates/function entirely instead of retaining unverified input synthesis. A future direct-resume design should use a newly proven, narrower vanilla close/resume mechanism rather than silently restoring this experiment.

## Current accepted model

1. KCD2 is the only pause owner.
2. `Menu@0::IsVisible()` proves the pause lifecycle.
3. `Menu@0::Render()` suppression removes only the visible pause menu.
4. Gameplay and vanilla-pause HUD child visibility are stored as separate bool snapshots.
5. `GetMovieClip()` handles are call-local borrowed pointers only.
6. Clean Pause restores gameplay child visibility.
7. Escape/Start or B restores vanilla-pause child visibility and reveals the normal menu.
8. Any unresolved state fails open to ordinary visible vanilla pause behavior.
