# Current status and plan

## Release status

**v0.1.0 is release-ready for KCD2 1.5.6 Windows retail**, primarily the PC Xbox Store / Xbox app build.

The production implementation is in `native/src/clean_pause_native.cpp`; the temporary rc7 generator/candidate pipeline has been removed.

## v0.1.0 product contract

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  Escape / Xbox Start -> visible vanilla pause menu
  Xbox B               -> visible vanilla pause menu
```

The vanilla pause menu then uses normal KCD2 controls to resume or perform menu actions.

Direct `Clean Pause -> B -> Running` is **not** part of v0.1.0. Retail testing showed B revealing the menu, and that behavior was explicitly accepted for this release. The unverified synthetic pause-key replay experiment has therefore been removed from production instead of being shipped as dead/risky code.

## Retail-proven behavior

On Xbox Store KCD2 1.5.6:

- first Start enters a real vanilla-owned pause without drawing the pause menu;
- world simulation stops;
- audio pauses like the ordinary KCD2 pause;
- subtitles can remain visible during Clean Pause;
- second Start reveals the already-open vanilla pause menu without an intermediate gameplay tick;
- B from Clean Pause reveals the same vanilla pause menu;
- the visible menu can then be closed normally;
- the rc7e and rc7f crash regressions are not present in rc7g.

## Accepted architecture

1. KCD2 is the sole pause owner.
2. The physical Escape/Start input is forwarded to KCD2.
3. `Menu@0::IsVisible()` is the independent retail pause-lifecycle signal.
4. Menu visibility is never changed by the mod.
5. Clean Pause suppresses only `Menu@0::Render()`.
6. Gameplay HUD presentation is preserved using two 28-value bool snapshots: gameplay state and vanilla-pause state.
7. `IUIElement::GetMovieClip()` pointers are borrowed/call-local: never retained and never released by the mod.
8. `hud@0::Update(float)` performs only bounded main-thread HUD maintenance during the pause transition.
9. Only `ClearSubtitles` and `HideNarrativeSubtitles` are suppressed for subtitle lifetime protection.
10. B/second Start restore the captured vanilla-pause HUD state before revealing the normal menu.
11. Unresolved state fails open to visible vanilla pause.

## Permanent rejected paths

Do not reintroduce without new direct retail evidence:

- action-map/profile replacement as the primary pause route;
- runtime action-map reload/remapping or `Player.OnAction` replacement;
- inferred/native/Lua custom `PauseGame` ownership;
- `only_ui` as vanilla pause ownership evidence;
- hiding `Menu@0` with `SetVisible(false)`;
- fixed libKCD2 WHGame RVAs across storefronts;
- aggressive writable-section `S_GameContext` scanning;
- root/global HUD visibility as complete HUD presentation;
- retaining raw `GetMovieClip()` pointers across frames;
- calling `Release()` on `IUIElement::GetMovieClip()` results;
- HUD child mutation from `Menu@0::Render()`;
- inferred contiguous XInput key IDs.

## Post-v0.1.0 work

These are improvements/extra validation, not blockers for the initial stable release:

- investigate a safe direct B resume only if it can be implemented without synthetic/unverified input replay;
- longer dialogue/subtitle lifetime testing;
- in-engine cutscene coverage;
- repeated-cycle, load-transition, Alt-Tab, and controller-reconnect robustness;
- revalidate ABI facts when KCD2 changes from 1.5.6.

## Decision rule

> Reuse vanilla KCD2 pause ownership, suppress only the menu rendering, preserve the exact HUD child presentation, and prefer a visible vanilla-menu fallback over unverified resume tricks.
