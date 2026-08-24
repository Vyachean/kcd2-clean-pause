# v0.1.0-rc.7c — HUD-preserving candidate

Prerelease candidate for Kingdom Come: Deliverance II 1.5.6 Windows retail, primarily tested on the PC Xbox Store/Xbox app build.

## Proven foundation

- KCD2 itself owns the real vanilla pause.
- `Menu@0::IsVisible()` is used as the verified pause lifecycle signal.
- Only `Menu@0::Render()` is suppressed to hide the pause menu.
- World simulation and audio pause correctly.
- A second Escape/Start reveals the already-open vanilla pause menu without an unpause/re-pause cycle.

## rc7c experiment

This candidate additionally:

- restores the global HUD visibility gate through `IFlashUI::SetHudElementsVisible(true)`;
- hooks `hud@0` named Flash calls and suppresses only `ClearSubtitles` / `HideNarrativeSubtitles` during Clean Pause;
- contains a B-resume route that consumes physical Xbox B and replays the captured vanilla pause press/release pair.

## Known retail result

The rc7c retail session showed **no visible HUD/subtitle improvement over rc7b**. The `hud@0` hook installed successfully and intercepted `hud.ClearSubtitles`, proving that part of the route, but the actual HUD remained hidden.

Therefore the hypothesis that the global HUD visibility gate alone is sufficient is rejected. The next candidate will hold the concrete `hud@0` element visible as well.

Direct B resume remains unverified in this exact session because the supplied log contains Escape interactions only and no physical Xbox B attempt while Clean Pause was active.

## Safety

This candidate does not use:

- custom/inferred `PauseGame`;
- `only_ui` ownership checks;
- action-map mutation;
- fixed libKCD2 WHGame RVAs;
- `Menu@0::SetVisible(false)`.

Unresolved runtime conditions fail open to ordinary visible vanilla pause behavior.

See `docs/STATUS_AND_PLAN.md`, `docs/REJECTED_HYPOTHESES.md`, and `docs/RETAIL_EVIDENCE_RC7C.md` for the current evidence ledger.