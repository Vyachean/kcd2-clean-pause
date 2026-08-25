# Current status and plan

## Release status

**v0.1.0 is the current stable release for KCD2 1.5.6 Windows retail**, primarily the PC Xbox Store / Xbox app build.

**v0.1.1-rc.3** is the current prerelease line. It retains the dual native packaging introduced in rc.1 and adds bounded presentation/safety improvements:

- `KCD2CleanPause.asi` for a shared ASI-loader installation;
- standalone `version.dll` for the existing self-contained installation;
- process-wide duplicate-load protection if both Clean Pause editions are accidentally present;
- blur-free Clean Pause presentation with exact DoF-state restoration.

rc.2 is superseded and must not be used for testing. Its blur controller called nonexistent Lua API `System.GetCVarValue`, so the DoF capability check failed and retail correctly fell open to the ordinary visible pause menu. rc.3 uses CryEngine's actual `System.GetCVar` getter.

The standalone loading path is already retail-proven through v0.1.0. Before v0.1.1 stable, the ASI loading path still needs [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md), and the corrected rc.3 DoF presentation path needs one retail confirmation on the primary Xbox Store 1.5.6 target.

The production runtime is in `native/src/clean_pause_native.cpp`; both editions compile that same runtime plus the same bounded blur controller and differ only in bootstrap/loading.

## Product contract

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  sharp retained frame, no pause DoF blur
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
- subtitles can remain visible during Clean Pause;
- second Start reveals the already-open vanilla pause menu without an intermediate gameplay tick;
- B from Clean Pause reveals the same vanilla pause menu;
- the visible menu can then be closed normally;
- the rc7e and rc7f crash regressions are not present in rc7g.

The rc.2 retail attempt did not exercise blur suppression because its invalid Lua getter forced the designed visible-menu fail-open path. rc.3 corrects the getter and remains to be confirmed once in retail.

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
9. Only `ClearSubtitles` and `HideNarrativeSubtitles` are suppressed for subtitle lifetime protection.
10. Clean Pause reads the current `wh_cl_NearDof` and `r_DepthOfField` through `System.GetCVar`, sets both to `0` only for hidden-menu presentation, and restores the saved values before visible vanilla presentation resumes.
11. B/second Start restore captured DoF and vanilla-pause HUD state before revealing the normal menu.
12. Unresolved state fails open to visible vanilla pause; transient DoF restoration failure remains retryable.

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

## Before v0.1.1 stable

- build v0.1.1-rc.3 in both package editions;
- in one optimized Xbox Store KCD2 1.5.6 session, confirm Clean Pause is sharp and the visible vanilla menu/gameplay restores the prior DoF behavior;
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
