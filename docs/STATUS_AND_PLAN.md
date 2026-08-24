# Current status and plan

This is the canonical project-status document. Detailed rejected/superseded hypotheses are kept in `docs/REJECTED_HYPOTHESES.md`; retail evidence is kept in `docs/RETAIL_EVIDENCE_*.md`.

## Target UX

Primary target:

- Kingdom Come: Deliverance II 1.5.6;
- Windows retail, primarily PC Xbox Store / Xbox app / Game Pass;
- Xbox controller, with keyboard Escape behaving analogously to Xbox Menu / Start.

Required behavior:

```text
Running
  Escape / Start -> Clean Pause

Clean Pause
  B              -> Running
  Escape / Start -> visible vanilla pause menu
```

Clean Pause must stop gameplay, dialogue/in-engine-cutscene progression, relevant audio, and subtitle lifetime while leaving the current rendered frame unobscured. No replacement overlay.

The strong depth-of-field blur applied by KCD2's vanilla pause is accepted and out of scope.

## Accepted pause foundation

KCD2 remains the **only pause owner**.

1. Forward the real physical Escape / Xbox Start event to vanilla KCD2.
2. Resolve `Menu@0` through `IFlashUI`.
3. Use `Menu@0::IsVisible()` as the independent retail-proven vanilla pause lifecycle signal.
4. Never mutate Menu visibility while Clean Pause is active.
5. Suppress only `Menu@0::Render()` to remove the visible pause menu.
6. A second Escape/Start restores Menu rendering and reveals the already-open vanilla menu without an unpause/re-pause tick.
7. Consume unrelated gameplay/dialog/cutscene input only while verified vanilla pause ownership exists.
8. Any unresolved state fails open to ordinary visible vanilla pause/input behavior.

This foundation was proven repeatedly by rc7b and remained stable through rc7c/rc7d.

## Latest retail result — rc7d rejected as HUD solution

The rc7d retail session reported no visible improvement over rc7c.

Runtime evidence nevertheless proved that rc7d's intended root visibility mechanisms were active:

- `hud@0` subtitle hook active;
- concrete `hud@0::SetVisible` hook active;
- global HUD visibility hook active;
- `hud@0::IsVisible() == true` verified on every Clean Pause entry;
- `Menu@0::Render()` suppression active.

The user still saw no HUD/hints/subtitles.

Therefore both of these are now rejected as HUD-restoration mechanisms:

- persistently preventing `IFlashUI::SetHudElementsVisible(false)`;
- persistently preventing `hud@0::SetVisible(false)` / forcing root `hud@0` visible.

`hud@0::IsVisible() == true` is **not** evidence that gameplay HUD child clips are visually enabled.

See `docs/RETAIL_EVIDENCE_RC7D.md`.

## Static explanation — KCD2 `C_UIHudMask`

Current libKCD2 1.5.6 reverse engineering identifies the missing layer.

KCD2 keeps one Flash movie named `hud`, but `C_UIHudMask` independently controls **28 named child movie clips** inside that still-visible root. It:

- tracks active framework UI sources (menus, dialogue, cutscenes, etc.);
- evaluates a per-widget rule table;
- stores a 28-bit current visibility set;
- pushes each widget's `name + bool` to its child movie clip inside `hud`.

This directly explains rc7d: the root can be visible while every relevant child has been disabled by the pause-menu UI source.

Verified child ids/names include:

- `Subtitles = 4`;
- `Hints = 7`;
- plus 26 other HUD widgets, for 28 total.

No fixed `C_UIHudMask` global/RVA is used by the candidate because libKCD2 addresses differ across storefront builds.

## Active candidate — v0.1.0-rc.7e

rc7e removes the rejected root HUD visibility hooks and works only through already-resolved `hud@0` plus verified interface vtables.

### Pre-pause HUD snapshot

Before KCD2 receives the physical pause press:

1. resolve `hud@0`;
2. resolve each of the 28 verified child names with `IUIElement::GetMovieClip(name)`;
3. read the actual child display state with `IFlashVariableObject::GetDisplayInfo`;
4. retain the engine-owned child wrappers for that Clean Pause attempt.

All 28 children must be captured successfully. Otherwise the candidate leaves vanilla behavior untouched.

### Pause presentation

After vanilla pause ownership is verified:

- restore exactly the **captured pre-pause visibility bool** for each child with `IFlashVariableObject::SetVisible`;
- do not force normally-hidden widgets visible;
- keep `hud@0` as the necessary parent container;
- briefly re-apply the 28-value snapshot from the existing Menu render transition hook for 750 ms so a late `C_UIHudMask` source refresh cannot immediately overwrite it;
- keep suppressing only `ClearSubtitles` and `HideNarrativeSubtitles` while Clean Pause owns presentation.

When Clean Pause ends, all retained `IFlashVariableObject` wrappers are released and normal KCD2 HUD rules resume.

### Xbox B root-cause fix

The rc7d log proves the retail controller ids:

- `xi_start = 516`;
- `xi_a = 526`;
- `xi_b = 527`.

The old enum incorrectly auto-incremented from 512 and compiled `XiA=522`, `XiB=523`. Thus physical B was logged and consumed, but **could never enter the B branch**. The absence of `B resume: replaying ...` in rc7d is fully explained by this enum error.

rc7e uses explicit retail-proven ids only. The pause-key replay mechanism remains **unverified, not rejected**; rc7e is the first build in which real `xi_b=527` can reach it.

## Proven retail facts

On Xbox Store KCD2 1.5.6:

- native bootstrap and raw `IInput::PostInputEvent` hook work;
- `Menu@0` resolves reliably;
- `Menu@0::IsVisible()` tracks vanilla pause open/close correctly;
- suppressing only `Menu@0::Render()` produces a real hidden vanilla pause;
- world simulation stops;
- audio pauses like ordinary vanilla pause;
- repeated Clean Pause entry works;
- second Escape/Start reveals the already-open vanilla pause menu while keeping pause continuous;
- `hud@0` resolves;
- named HUD `CallFunction` interception works;
- `hud.ClearSubtitles` can be intercepted;
- one-shot global HUD enable is insufficient;
- persistent global/root `hud@0` visibility holding is also insufficient;
- `hud@0::IsVisible()==true` does not imply visible child HUD presentation;
- Xbox retail key ids Start=516, A=526, B=527.

## Remaining retail gates

One normal rc7e session should answer the remaining product questions:

1. Does the exact pre-pause 28-child snapshot preserve visible HUD/hints?
2. During dialogue, does the same subtitle remain visible beyond its normal lifetime while speech/audio remain paused?
3. Does physical Xbox B now enter the replay route and resume immediately without menu flash, skip, or cancel?
4. Does second Start/Escape still reveal ordinary vanilla pause continuously?
5. Does repeated use remain stable in the same session?

Do not request a separate launch for each item.

## Rejected/superseded mechanisms

Do not reintroduce these without new retail evidence that directly invalidates the recorded result:

- rc.1/rc.2 profile/action routing as primary pause interception;
- runtime partial action-map reload, persistent remapping, or `Player.OnAction` replacement;
- rc.4 inferred native `PauseGame` ABI;
- `CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, or Lua/custom PauseGame as production pause owner;
- `ActionMapManager.IsFilterEnabled("only_ui")` as pause ownership evidence;
- mutating `Menu@0` visibility to hide the pause menu;
- fixed libKCD2 WHGame RVAs for storefront-independent production lookup;
- aggressive writable-section `S_GameContext` / `C_UIMenu` scanning;
- one-shot `IFlashUI::SetHudElementsVisible(true)` as complete HUD restoration;
- persistent whole-HUD/global + `hud@0` root visibility holding as complete HUD restoration;
- `hud@0::IsVisible()` as proof of child HUD presentation;
- blocking `hud.ClearSubtitles` by itself as complete subtitle restoration;
- forwarding physical B directly to the hidden vanilla Menu as direct-resume solution;
- assuming KCD2 XInput `KeyId` values form one contiguous auto-incremented range.

See `docs/REJECTED_HYPOTHESES.md` for the detailed evidence.

## Active ABI facts

For KCD2 1.5.6:

- `SSystemGlobalEnvironment + 0x98` = `IGame*`;
- `SSystemGlobalEnvironment + 0x140` = `IFlashUI*`;
- `IInput::PostInputEvent` is the raw input route;
- `IFlashUI::GetUIElementByInstanceStr` = slot 18;
- `IUIElement::Render` = slot 24;
- `IUIElement::SetVisible` = slot 28;
- `IUIElement::IsVisible` = slot 29;
- named `IUIElement::CallFunction` = slot 69;
- `IUIElement::GetMovieClip(name)` = slot 71;
- `IFlashVariableObject::Release` = slot 0;
- `IFlashVariableObject::GetDisplayInfo` = slot 26;
- `IFlashVariableObject::SetVisible` = slot 33;
- retail `XiStart=516`, `XiA=526`, `XiB=527`.

The Flash child slots above are verified interface ABI from libKCD2 1.5.6, not fixed WHGame RVAs.

## Safety invariants

Release blocking:

- never call rejected/custom `PauseGame` routes;
- never use `only_ui` as ownership evidence;
- never mutate `Menu@0` visibility in the active architecture;
- never use fixed libKCD2 WHGame RVAs for production discovery;
- do not retain rc7d root HUD visibility hooks in rc7e;
- child snapshot must capture and replay pre-pause visibility rather than force all 28 children visible;
- all retained Flash variable wrappers must be released when ownership ends;
- physical B must not leak into gameplay/dialog/cutscene while Clean Pause owns input;
- nested/synthetic input generated during vanilla dispatch must forward exactly once and must not be interpreted as physical input;
- unresolved state must fail open.

## Release process

GitHub Releases are the canonical binary distribution channel.

Every retail-test candidate is published as a GitHub **prerelease** immediately after its push build passes:

1. generate the exact final C++ used for compilation;
2. run the static safety contract over that generated source and active ABI header;
3. build x64 Release with MSVC/static runtime;
4. validate proxy exports/dependencies;
5. package ZIP and `SHA256SUMS.txt`;
6. verify the downloaded CI artifact;
7. publish/update the prerelease;
8. bind the candidate tag to the exact successful push `GITHUB_SHA` and verify the remote tag.

Branch-level `cancel-in-progress` prevents an obsolete intermediate push from publishing after a newer one. Actions artifacts remain CI evidence, not the primary user-facing download surface.

## Retail-test policy

Game launches are expensive. Before asking for another launch:

1. close everything possible by source review/reverse engineering;
2. combine compatible hypotheses into one fail-open functional candidate;
3. instrument that candidate so one session distinguishes the remaining failure classes;
4. run CI and publish the GitHub prerelease first;
5. request one normal gameplay session, with dialogue/cutscene checks only if naturally available.

## Stable release gate

Stable `v0.1.0` remains blocked until retail confirms:

- first Start/Escape produces Clean Pause without the pause menu;
- HUD/hints remain visible;
- current subtitle remains visible beyond normal lifetime;
- dialogue/cutscene progression and audio pause coherently;
- B resumes directly without menu flash/skip/cancel;
- second Start/Escape reveals ordinary vanilla pause continuously;
- repeated use/load transitions/Alt-Tab/controller reconnect do not cause persistent input loss;
- all failure paths remain fail-open;
- installation/uninstallation and proxy-DLL conflict behavior are documented.

## Decision rule

> Reuse vanilla KCD2 pause ownership and preserve the exact pre-pause HUD child presentation while removing only the vanilla pause-menu render.
