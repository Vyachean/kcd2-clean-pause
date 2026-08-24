# v0.1.0-rc.7e — HUD child snapshot candidate

Prerelease candidate for Kingdom Come: Deliverance II 1.5.6 Windows retail, primarily tested against the PC Xbox Store/Xbox app build.

## What retail testing established before rc7e

The hidden-vanilla-pause foundation is already proven:

- KCD2 owns the real pause;
- `Menu@0::IsVisible()` tracks the vanilla pause lifecycle;
- only `Menu@0::Render()` is suppressed for Clean Pause;
- world simulation and audio stop;
- second Start/Escape reveals the already-open vanilla pause menu continuously.

rc7d then proved that whole-HUD visibility is **not** the missing presentation layer. Even with both root visibility hooks active and `hud@0::IsVisible() == true`, the HUD remained visually absent.

Static analysis of KCD2 1.5.6 identifies the deeper mechanism: `C_UIHudMask` computes visibility for 28 named child movie clips inside the still-visible `hud` Flash movie from the framework UI-source monitor.

## rc7e HUD change

rc7e removes the rejected root HUD visibility hooks.

Before the physical pause press is forwarded to KCD2 it:

1. resolves `hud@0` through the already-proven `IFlashUI` route;
2. resolves all 28 verified HUD child names through `IUIElement::GetMovieClip`;
3. reads each child's actual pre-pause display visibility through `IFlashVariableObject::GetDisplayInfo`;
4. retains the engine-owned child wrappers only for the lifetime of that Clean Pause attempt.

After vanilla pause becomes active it restores **exactly the captured visibility value for each child**, rather than forcing all HUD widgets visible. The snapshot is briefly re-applied from the existing Menu render hook during the transition so a late `C_UIHudMask` source refresh cannot immediately overwrite it.

The narrow subtitle lifetime guard remains and suppresses only:

- `ClearSubtitles`;
- `HideNarrativeSubtitles`.

All other HUD Flash calls remain vanilla.

## Xbox B fix

The rc7d log proved the old enum was wrong:

- Start = 516;
- A = 526;
- B = 527.

The previous contiguous enum compiled B as 523, so physical `xi_b` never entered the B-resume branch. rc7e uses only explicit retail-proven values.

Physical B is consumed while Clean Pause owns input and replays the captured physical pause press/release pair through the original `PostInputEvent`. The replay mechanism itself remains retail-unverified until this candidate is tested.

## Safety

rc7e does not use:

- custom/inferred `PauseGame`;
- `only_ui` ownership checks;
- action-map mutation;
- fixed libKCD2 WHGame RVAs;
- `Menu@0::SetVisible(false)`;
- persistent `SetHudElementsVisible(false)` suppression;
- persistent `hud@0::SetVisible(false)` suppression.

The child snapshot uses verified KCD2 1.5.6 interface slots only:

- `IUIElement::GetMovieClip(name)` = 71;
- `IFlashVariableObject::Release` = 0;
- `IFlashVariableObject::GetDisplayInfo` = 26;
- `IFlashVariableObject::SetVisible` = 33.

If all 28 child states cannot be captured or restored, Clean Pause fails open to ordinary visible vanilla pause behavior.

## Retail acceptance

Use one normal session. Highest-value checks:

1. A HUD/hint visible immediately before pause remains visible during Clean Pause.
2. A currently visible spoken subtitle remains visible beyond its normal lifetime while audio/dialogue are stopped.
3. Xbox B resumes directly without showing the menu and without cancel/skip side effects.
4. Second Start/Escape still reveals ordinary vanilla pause continuously.

Do not perform an extra launch solely for an optional cutscene case. Send one fresh native log if any required behavior fails.

See `docs/STATUS_AND_PLAN.md`, `docs/REJECTED_HYPOTHESES.md`, and `docs/RETAIL_EVIDENCE_RC7D.md` for the evidence ledger.
