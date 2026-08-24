# Rejected hypotheses and retail evidence

A rejected path must not be reintroduced without new direct retail evidence.

## Pause ownership

Rejected:

- profile/action routing as the primary pause interception path;
- runtime action-map reload/remapping or `Player.OnAction` replacement;
- inferred native `PauseGame` ABI;
- `CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, Lua/custom PauseGame as production owner;
- `ActionMapManager.IsFilterEnabled("only_ui")` as vanilla-pause evidence;
- `Menu@0::SetVisible(false)` as hidden-pause ownership architecture;
- fixed libKCD2 WHGame RVAs for storefront-independent lookup;
- aggressive writable-section `S_GameContext` / `C_UIMenu` scanning.

Accepted foundation:

- KCD2 owns pause;
- real Escape/Start is forwarded;
- `Menu@0::IsVisible()` is the retail lifecycle signal;
- Menu visibility is untouched;
- `Menu@0::Render()` alone is suppressed during Clean Pause;
- rc7g confirms first-pause stability, second-Start menu reveal and normal exit from the visible vanilla menu.

## HUD presentation

Rejected:

- one-shot global HUD visibility restore;
- persistent global HUD gate holding;
- persistent `hud@0::SetVisible(false)` suppression;
- `hud@0::IsVisible()==true` as proof that gameplay child HUD is visible;
- `ClearSubtitles` suppression alone as complete subtitle restoration;
- forcing all HUD children visible.

Accepted retail finding:

- KCD2's 28 child HUD movie clips are the relevant presentation layer;
- rc7e first restored the current subtitle at the bottom during Clean Pause;
- rc7g reconfirmed visible subtitles while also remaining stable through Clean Pause -> visible vanilla menu -> normal exit.

## Movieclip pointer ownership

### Persist raw `IUIElement::GetMovieClip()` pointers across frames

Rejected after rc7e code audit.

Even though rc7e visibly restored subtitles, keeping raw movieclip pointers in global snapshot state across render/input/UI transitions creates stale-pointer and cross-thread lifetime risk.

Permanent rule: snapshots store only visibility bools, never movieclip pointers.

### Call `Release()` on every `IUIElement::GetMovieClip()` result

Rejected by rc7f retail evidence.

rc7f changed to immediate `Release()` after each capture/restore access. On the first pause the log reached:

```text
HUD visibility snapshot captured for all 28 clips (gameplay-pre-pause)
Clean Pause subtitle freeze: suppressed hud.ClearSubtitles
```

and then the game crashed before vanilla-pause snapshot capture or Clean Pause entry.

CryEngine's documented IUIElement usage shows `GetMovieClip()` as a directly usable returned pointer without a caller `Release()` requirement. The documentation separately requires caller Release for variable objects created through raw `IFlashPlayer` APIs. libKCD2 confirms `IFlashVariableObject::Release()` is destructive.

### Borrowed/call-local `GetMovieClip()` handles

**Accepted after rc7g retail validation.**

RC7g uses this rule:

- treat result as borrowed/cached;
- use only inside the current helper call;
- do not retain it;
- do not call `Release()` on it;
- store only child visibility bools.

The user confirmed rc7g successfully enters Clean Pause with visible subtitles, reveals vanilla pause on the second pause press, and can then exit the visible pause normally without the rc7e/rc7f crashes.

Do not replace this ownership model without new evidence.

## Render/update lifecycle

Rejected:

- HUD child acquisition/mutation/release from `Menu@0::Render()`.

`Menu::Render()` must remain presentation-only.

The active bounded maintenance route is verified `hud@0::Update(float)` slot 23, with original Update forwarded first and child mutation allowed only on the validated main thread. RC7g's successful first pause confirms this route is no longer a current crash blocker.

## Input findings

Rejected:

- forwarding physical Xbox B directly to hidden vanilla Menu as the direct-resume solution;
- assuming KCD2 XInput ids are contiguous.

Retail-proven ids:

- Start = 516;
- A = 526;
- B = 527.

Direct B via replayed vanilla pause-key pair remains **unverified, not rejected**. The successful rc7g report covers exit from an already-visible vanilla menu, not direct B from Clean Pause.

## Current accepted model

1. KCD2 remains the only pause owner.
2. `Menu@0::IsVisible()` proves pause lifecycle.
3. `Menu@0::Render()` suppression removes only the visible pause menu.
4. The exact 28 child HUD visibility bools are captured before pause.
5. A second vanilla-pause bool snapshot is captured after KCD2 opens pause.
6. `GetMovieClip()` handles are call-local borrowed pointers only and are not released by the mod.
7. Clean Pause restores gameplay bools.
8. Second Start restores vanilla-pause bools before revealing Menu.
9. RC7g retail confirms steps 1-8 work through normal visible-menu exit while keeping subtitles visible.
10. Direct B restores vanilla-pause bools before replaying the vanilla pause toggle, but this direct path still requires retail proof.
11. Any unresolved state fails open.
