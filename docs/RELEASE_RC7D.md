# v0.1.0-rc.7d — concrete HUD visibility candidate

Prerelease candidate for Kingdom Come: Deliverance II 1.5.6 Windows retail, primarily tested against the PC Xbox Store/Xbox app build.

## Why rc7d exists

rc7b proved the hidden-vanilla-pause foundation: KCD2 owns the real pause, `Menu@0` remains logically open, and only `Menu@0::Render()` is suppressed.

rc7c then proved that `hud@0` resolves and its named Flash calls can be intercepted, but `IFlashUI::SetHudElementsVisible(true)` alone did **not** make HUD/subtitles visible. That hypothesis is now rejected.

## rc7d change

rc7d adds concrete HUD-element visibility control while preserving the accepted pause architecture:

- before the real pause event is forwarded, hook the generic `IUIElement::SetVisible` implementation;
- suppress `SetVisible(false)` only when `this` is the already-verified `hud@0` and vanilla pause acquisition/Clean Pause is active;
- forward every visibility call for `Menu@0` and every other UI element unchanged;
- after vanilla pause acquisition, enable the global HUD gate and explicitly set `hud@0` visible;
- require `hud@0::IsVisible() == true` before accepting Clean Pause presentation ownership;
- keep the narrow `hud.ClearSubtitles` / `hud.HideNarrativeSubtitles` suppression as a secondary lifetime safeguard;
- when switching to the ordinary visible vanilla pause menu, relinquish Clean Pause first and restore the normal HUD-hidden pause presentation.

The strong vanilla pause depth-of-field blur remains intentionally out of scope.

## B resume

The captured-pause-key replay route from rc7c remains present. Physical Xbox B is consumed while Clean Pause owns input and is not forwarded to dialog/cutscene/gameplay action maps. Resume is accepted only if `Menu@0::IsVisible()` becomes false; otherwise the candidate fails open to the ordinary visible vanilla pause menu.

This route is still classified as **retail-unverified** until a session log contains an actual physical B attempt.

## Safety

This candidate does not use:

- custom/inferred `PauseGame`;
- `only_ui` ownership checks;
- action-map mutation;
- fixed libKCD2 WHGame RVAs;
- `Menu@0::SetVisible(false)`.

The concrete visibility hook may suppress only `hud@0` hide calls; all other elements and `SetVisible(true)` calls forward to the original engine method.

See `docs/STATUS_AND_PLAN.md` and `docs/REJECTED_HYPOTHESES.md` for the current evidence ledger.