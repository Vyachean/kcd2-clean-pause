# Current status and plan

## Release status

**v0.1.0 is the current stable release for KCD2 1.5.6 Windows retail**, primarily the PC Xbox Store / Xbox app build.

**v0.1.1-rc.4** is the current development prerelease line. It retains the dual native packaging introduced in rc.1 and adds bounded presentation/safety improvements:

- `KCD2CleanPause.asi` for a shared ASI-loader installation;
- standalone `version.dll` for the existing self-contained installation;
- process-wide duplicate-load protection if both Clean Pause editions are accidentally present;
- blur-free Clean Pause presentation with exact DoF-state restoration;
- preservation of active NPC speech bubbles / overhead subtitles across the vanilla pause transition.

rc.2 is superseded and must not be used for testing. Its blur controller called nonexistent Lua API `System.GetCVarValue`, so the DoF capability check failed and retail correctly fell open to the ordinary visible pause menu. rc.3 corrected this to CryEngine's actual `System.GetCVar` getter.

The corrected rc.3 blur path is retail-confirmed on the primary Xbox Store 1.5.6 target: the first Xbox Start enters Clean Pause and the retained frame is sharp with the pause DoF blur removed. rc.4 adds overhead-bubble preservation and requires one focused retail observation while an NPC overhead subtitle is currently visible.

The standalone loading path is already retail-proven through v0.1.0. Before v0.1.1 stable, the ASI loading path still needs [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md), the DoF restoration handoff needs explicit retail confirmation, the rc.4 overhead-bubble path needs retail confirmation, and one shared-loader coexistence case remains required.

The production runtime is in `native/src/clean_pause_native.cpp`; both editions compile that same runtime plus the same bounded blur and overhead-bubble controllers and differ only in bootstrap/loading.

## Product contract

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  sharp retained frame, no pause DoF blur
  visible dialogue subtitles remain visible
  active NPC overhead subtitles remain visible
  Escape / Xbox Start -> visible vanilla pause menu
  Xbox B               -> visible vanilla pause menu
```

The vanilla pause menu then uses normal KCD2 controls to resume or perform menu actions. The user's original DoF settings are restored before normal visible-menu presentation resumes.

Direct `Clean Pause -> B -> Running` is **not** part of the current contract. Retail testing showed B revealing the menu, and that behavior was explicitly accepted. The unverified synthetic pause-key replay experiment remains removed from production.

## Retail-proven behavior

On Xbox Store KCD2 1.5.6 using the standalone loading path, the v0.1.0 pause/HUD mechanism proved that:

- first Start enters a real vanilla-owned pause without drawing the pause menu;
- world simulation stops;
- audio pauses like the ordinary KCD2 pause;
- dialogue subtitles can remain visible during Clean Pause;
- second Start reveals the already-open vanilla pause menu without an intermediate gameplay tick;
- B from Clean Pause reveals the same vanilla pause menu;
- the visible menu can then be closed normally;
- the rc7e and rc7f crash regressions are not present in rc7g.

The rc.2 retail attempt did not exercise blur suppression because its invalid Lua getter forced the designed visible-menu fail-open path.

The rc.3 retail attempt confirmed the corrected blur entry path: Xbox Start enters Clean Pause and the retained frame is sharp with the vanilla pause DoF blur removed. That observation does not by itself claim that the subsequent visible-menu/gameplay DoF restoration handoff was tested in the same pass.

The rc.4 overhead-bubble path is not yet retail-confirmed. Static reverse-engineering evidence shows that `C_UIHudBubbles` owns separate bubble IDs / Flash objects underneath the root `Bubbles` HUD clip, explaining why the existing 28-child visibility snapshot cannot restore an overhead line once vanilla pause releases it.

## Dual-package architecture

The editions are mutually exclusive installations of the same runtime:

```text
ASI loader -> KCD2CleanPause.asi -> clean_pause::Start()

KCD2 -> version.dll proxy -> clean_pause::Start()
```

The ASI edition exists to avoid the hard file-name conflict when another mod already owns `version.dll`. The standalone edition remains available for users who want no separate ASI-loader dependency.

Do not intentionally install both Clean Pause editions together. A process-wide guard prevents the second copy from installing duplicate hooks if both are accidentally loaded.

## Accepted runtime architecture

1. KCD2 is the sole pause owner.
2. The physical Escape/Start input is forwarded to KCD2.
3. `Menu@0::IsVisible()` is the independent retail pause-lifecycle signal.
4. Menu visibility is never changed by the mod.
5. Clean Pause suppresses only `Menu@0::Render()`.
6. Gameplay HUD presentation is preserved using two 28-value bool snapshots: gameplay state and vanilla-pause state.
7. `IUIElement::GetMovieClip()` pointers are borrowed/call-local: never retained and never released by the mod.
8. `hud@0::Update(float)` performs only bounded main-thread HUD maintenance during the pause transition.
9. Only `ClearSubtitles` and `HideNarrativeSubtitles` are suppressed for normal subtitle lifetime protection.
10. NPC overhead subtitles are handled separately: `C_UIHudBubbles` is discovered from the live `hud@0` listener list through MSVC RTTI, without fixed `WHGame.dll` RVAs.
11. While vanilla `Menu@0` is logically visible, only `I_UIHudBubbles::UpdateBubbles()` and `ReleaseBubble()` are frozen. The freeze starts before vanilla `SetVisible(true)` and ends after `SetVisible(false)` returns.
12. Bubble discovery is optional/fail-open and cannot disable the proven Clean Pause path if the concrete listener layout cannot be validated.
13. Clean Pause reads the current `wh_cl_NearDof` and `r_DepthOfField` through `System.GetCVar`, sets both to `0` only for hidden-menu presentation, and restores the saved values before visible vanilla presentation resumes.
14. B/second Start restore captured DoF and vanilla-pause HUD state before revealing the normal menu.
15. Unresolved core state fails open to visible vanilla pause; transient DoF restoration failure remains retryable.

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
- reconstructing overhead bubble text/anchors after vanilla has destroyed their state;
- retaining raw `GetMovieClip()` pointers across frames;
- calling `Release()` on `IUIElement::GetMovieClip()` results;
- HUD child mutation from `Menu@0::Render()`;
- inferred contiguous XInput key IDs.

## Before v0.1.1 stable

- build v0.1.1-rc.4 in both package editions;
- while an NPC overhead subtitle is visible, confirm first Start enters Clean Pause and that exact overhead line remains visible;
- confirm the overhead line does not become permanently stuck after closing the vanilla pause menu / resuming gameplay;
- confirm that second Start/B reveals the visible vanilla menu with normal DoF and that gameplay DoF remains unchanged after resume;
- run the ASI retail-equivalence checklist on Xbox Store KCD2 1.5.6;
- verify one shared-loader coexistence case with another real KCD2 ASI plugin;
- if those checks pass, promote the dual-package model to v0.1.1 stable.

## Later work

- investigate a safe direct B resume only if it can be implemented without synthetic/unverified input replay;
- longer dialogue/subtitle lifetime testing;
- in-engine cutscene coverage;
- repeated-cycle, load-transition, Alt-Tab, and controller-reconnect robustness;
- revalidate ABI facts when KCD2 changes from 1.5.6.

## Decision rule

> Reuse vanilla KCD2 pause ownership, suppress only the menu rendering, preserve exact presentation state, and prefer a visible vanilla-menu fallback over unverified resume tricks.
