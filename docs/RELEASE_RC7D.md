# v0.1.0-rc.7d — dual HUD visibility candidate

Prerelease candidate for Kingdom Come: Deliverance II 1.5.6 Windows retail, primarily tested against the PC Xbox Store/Xbox app build.

## Why rc7d exists

rc7b proved the hidden-vanilla-pause foundation: KCD2 owns the real pause, `Menu@0` remains logically open, and only `Menu@0::Render()` is suppressed.

rc7c then proved that `hud@0` resolves and its named Flash calls can be intercepted, but a one-shot `IFlashUI::SetHudElementsVisible(true)` after pause acquisition did **not** make HUD/subtitles visible. That one-shot hypothesis is rejected.

## rc7d change

rc7d holds both known HUD visibility layers during vanilla pause acquisition and Clean Pause:

- hook `IFlashUI::SetHudElementsVisible` before forwarding the real pause event;
- suppress only `SetHudElementsVisible(false)` while pause acquisition/Clean Pause owns presentation;
- hook the generic `IUIElement::SetVisible` implementation;
- suppress `SetVisible(false)` only when `this` is the already-verified `hud@0` and pause acquisition/Clean Pause is active;
- forward every `true` call, every Menu visibility call, and every call for other UI elements unchanged;
- after vanilla pause acquisition, explicitly enable the global HUD gate and set `hud@0` visible;
- require `hud@0::IsVisible() == true` before accepting Clean Pause presentation ownership;
- keep the narrow `hud.ClearSubtitles` / `hud.HideNarrativeSubtitles` suppression as a secondary subtitle-lifetime safeguard;
- when switching to ordinary visible vanilla pause, relinquish Clean Pause first so the original HUD-hide calls can run again.

The strong vanilla pause depth-of-field blur remains intentionally out of scope.

## B resume

The captured-pause-key replay route remains present. Physical Xbox B is consumed while Clean Pause owns input and is not forwarded to dialog/cutscene/gameplay action maps. Resume is accepted only if `Menu@0::IsVisible()` becomes false; otherwise the candidate fails open to the ordinary visible vanilla pause menu.

This route is still **retail-unverified** because the rc7c log contained Escape interactions only and no physical B attempt.

## Safety

This candidate does not use:

- custom/inferred `PauseGame`;
- `only_ui` ownership checks;
- action-map mutation;
- fixed libKCD2 WHGame RVAs;
- `Menu@0::SetVisible(false)`.

The global hook may suppress only `IFlashUI::SetHudElementsVisible(false)` while pending/clean. The concrete hook may suppress only `hud@0::SetVisible(false)` while pending/clean. All `true` calls and all unrelated objects forward to the original engine methods.

## Release integrity

The same push workflow that builds and checksum-verifies the candidate publishes the prerelease and then force-binds `v0.1.0-rc.7d` to that workflow's exact `GITHUB_SHA`. The job verifies the remote tag immediately after pushing it. `VERSION`, source tree, release tag, ZIP, and checksum must therefore describe the same verified candidate snapshot.

See `docs/STATUS_AND_PLAN.md` and `docs/REJECTED_HYPOTHESES.md` for the current evidence ledger.
