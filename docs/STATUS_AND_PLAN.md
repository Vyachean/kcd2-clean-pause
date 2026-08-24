# Current status and plan

This is the canonical project-status document. Detailed rejected/superseded hypotheses are kept in `docs/REJECTED_HYPOTHESES.md`; retail evidence is kept in `docs/RETAIL_EVIDENCE_*.md` where useful.

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
6. A second Escape/Start restores Menu rendering and reveals the already-open vanilla pause menu without an unpause/re-pause tick.
7. Consume unrelated gameplay/dialog/cutscene input only while verified vanilla pause ownership exists.
8. Any unresolved state fails open to ordinary visible vanilla pause/input behavior.

This foundation was proven repeatedly by rc7b and remained stable in rc7c.

## Active candidate — v0.1.0-rc.7d

rc7c proved that a **one-shot** `IFlashUI::SetHudElementsVisible(true)` is not enough: the user saw no visible HUD/subtitle improvement even though `hud@0` resolved and `hud.ClearSubtitles` was intercepted.

rc7d therefore holds both known HUD visibility layers during vanilla pause acquisition and Clean Pause:

### Global HUD gate

Before forwarding the real pause event, hook `IFlashUI::SetHudElementsVisible`.

While pause acquisition is pending or Clean Pause owns presentation:

- `SetHudElementsVisible(false)` for the verified `g_flashUI` is suppressed;
- every `SetHudElementsVisible(true)` forwards to the original engine implementation;
- once Clean Pause is relinquished, normal vanilla `false` calls are allowed again.

This is **not** a resurrection of the rejected rc7c hypothesis. The rejected hypothesis was that one `true` call after pause acquisition was sufficient. Persistent false-call suppression combined with concrete HUD visibility is a new, unverified mechanism.

### Concrete `hud@0`

Before forwarding the pause event, also hook the generic `IUIElement::SetVisible` implementation.

While pending/clean:

- suppress `SetVisible(false)` only when `this ==` the already-resolved `hud@0`;
- forward every `SetVisible(true)`;
- forward every visibility call for Menu and every other UI element.

After vanilla pause acquisition:

- explicitly set the global HUD gate true;
- explicitly set `hud@0` visible;
- require `hud@0::IsVisible() == true` before accepting Clean Pause presentation ownership.

### Subtitle lifetime safeguard

Keep the narrow named HUD `CallFunction` hook that suppresses only:

- `ClearSubtitles`;
- `HideNarrativeSubtitles`.

All other HUD Flash calls forward unchanged.

This safeguard alone is known to be insufficient; rc7c proved that an intercepted `ClearSubtitles` does not help while the HUD remains hidden.

### B resume

Physical Xbox B is consumed while Clean Pause owns input and must not reach `dialog_cancel`, `cutscene_skip`, or gameplay.

The candidate replays the exact captured physical pause press/release pair through the original `PostInputEvent` route. Resume is accepted only when `Menu@0::IsVisible()` becomes false. Otherwise render suppression is removed and ordinary visible vanilla pause is shown.

This route remains **retail-unverified** because the supplied rc7c session contained Escape interactions only and no physical B attempt.

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
- a one-shot global HUD visibility enable is not sufficient to restore visible HUD/subtitles.

## Remaining retail gates

One normal rc7d session should answer all remaining product questions:

1. Does dual global+concrete HUD holding leave HUD/hints visible?
2. During dialogue, does the same subtitle remain visible beyond its normal lifetime while speech/audio remain paused?
3. Does physical Xbox B resume immediately without menu flash, skip, or cancel?
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
- one-shot `IFlashUI::SetHudElementsVisible(true)` as a complete HUD restoration mechanism;
- blocking `hud.ClearSubtitles` by itself as a complete subtitle restoration mechanism;
- forwarding physical B directly to the hidden vanilla Menu as the direct-resume solution.

See `docs/REJECTED_HYPOTHESES.md` for evidence and distinctions.

## Active ABI facts

For KCD2 1.5.6:

- `SSystemGlobalEnvironment + 0x98` = `IGame*`;
- `SSystemGlobalEnvironment + 0x140` = `IFlashUI*`;
- `IInput::PostInputEvent` is the raw input route;
- `IFlashUI::GetUIElementByInstanceStr` = slot 18;
- `IFlashUI::SetHudElementsVisible` = slot 28;
- `IUIElement::Render` = slot 24;
- `IUIElement::SetVisible` = slot 28;
- `IUIElement::IsVisible` = slot 29;
- named `IUIElement::CallFunction` = slot 69.

## Safety invariants

Release blocking:

- never call rejected/custom `PauseGame` routes;
- never use `only_ui` as ownership evidence;
- never mutate `Menu@0` visibility in the active architecture;
- never use fixed libKCD2 WHGame RVAs for production discovery;
- global HUD hook may suppress only `SetHudElementsVisible(false)` for the verified FlashUI while pending/clean;
- concrete HUD hook may suppress only `SetVisible(false)` for the verified `hud@0` while pending/clean;
- all `true` calls and unrelated objects must forward;
- physical B must not leak into gameplay/dialog/cutscene while Clean Pause owns input;
- nested/synthetic input generated during vanilla dispatch must forward exactly once and must not be interpreted as physical input;
- unresolved state must fail open.

## Release process

GitHub Releases are the canonical binary distribution channel.

Every retail-test candidate is published as a GitHub **prerelease** immediately after its push build passes:

1. generate the exact final C++ used for compilation;
2. run the static safety contract over that generated source;
3. build x64 Release with MSVC/static runtime;
4. validate proxy exports/dependencies;
5. package ZIP and `SHA256SUMS.txt`;
6. verify the downloaded CI artifact;
7. publish/update the prerelease;
8. bind the candidate tag to the exact successful push `GITHUB_SHA` and verify the remote tag.

Branch-level `cancel-in-progress` prevents an obsolete intermediate push from publishing after a newer one.

Actions artifacts remain CI evidence, not the primary user-facing download surface.

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

> Reuse vanilla KCD2 pause ownership and remove only the visual obstruction.
