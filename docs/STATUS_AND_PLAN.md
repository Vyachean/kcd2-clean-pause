# Current status and plan

## Release status

**v0.1.0 is the current stable release for KCD2 1.5.6 Windows retail**, primarily the PC Xbox Store / Xbox app build.

**v0.2.0-rc.1** is the current development release candidate. It is the first release under the normalized SemVer policy and consolidates the feature work that was previously published incrementally as `v0.1.1-rc.1` through `v0.1.1-rc.4`.

The `0.2.0` feature set adds:

- `KCD2CleanPause.asi` for a shared ASI-loader installation;
- standalone `version.dll` for the existing self-contained installation;
- process-wide duplicate-load protection if both Clean Pause editions are accidentally present;
- blur-free Clean Pause presentation with exact DoF-state restoration;
- preservation of active NPC speech bubbles / overhead subtitles across the vanilla pause transition.

The historical `v0.1.1-rc.1` through `v0.1.1-rc.4` tags remain immutable, but **no stable v0.1.1 is planned**. These are user-facing features and therefore belong to the next minor release, `v0.2.0`.

The blur-free entry path and overhead-subtitle preservation are retail-confirmed on the primary Xbox Store 1.5.6 target. Before stable `v0.2.0`, the ASI loading path still needs [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md), the DoF restoration handoff needs explicit retail confirmation, one longer post-resume bubble-lifetime observation remains useful, and one shared-loader coexistence case remains required.

The production runtime is in `native/src/clean_pause_native.cpp`; both editions compile that same runtime plus the bounded blur and overhead-bubble controllers and differ only in bootstrap/loading.

## Versioning / release model

The project now uses a conventional SemVer + Git tag flow:

- unreleased merged work remains under `Unreleased`;
- backward-compatible features before 1.0 bump MINOR (`0.1.0` -> `0.2.0`);
- fixes bump PATCH (`0.2.0` -> `0.2.1`);
- release candidates are numbered only for the same target release (`0.2.0-rc.1`, `0.2.0-rc.2`);
- merges to `main` build and validate but do not publish a GitHub Release;
- publication is triggered only by an immutable matching `v<VERSION>` tag.

See [RELEASE.md](RELEASE.md).

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

On Xbox Store KCD2 1.5.6 using the standalone loading path:

- first Start enters a real vanilla-owned pause without drawing the pause menu;
- world simulation stops;
- audio pauses like the ordinary KCD2 pause;
- dialogue subtitles can remain visible during Clean Pause;
- the retained frame is sharp with vanilla pause DoF removed;
- NPC overhead subtitles are preserved in Clean Pause together with the restored main HUD;
- second Start reveals the already-open vanilla pause menu without an intermediate gameplay tick;
- B from Clean Pause reveals the same vanilla pause menu;
- the visible menu can then be closed normally.

The earlier `v0.1.1-rc.2` attempt is superseded: its invalid Lua getter forced the designed visible-menu fail-open path. `v0.1.1-rc.3` corrected the getter, and `v0.1.1-rc.4` added the retail-confirmed overhead-bubble preservation now included in `v0.2.0-rc.1`.

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

## Before v0.2.0 stable

- publish `v0.2.0-rc.1` from its exact tag;
- confirm during normal play that an overhead line does not become permanently stuck after closing the vanilla pause menu / resuming gameplay;
- confirm that second Start/B reveals the visible vanilla menu with normal DoF and that gameplay DoF remains unchanged after resume;
- run the ASI retail-equivalence checklist on Xbox Store KCD2 1.5.6;
- verify one shared-loader coexistence case with another real KCD2 ASI plugin;
- if those checks pass, prepare and tag stable `v0.2.0` without creating unnecessary additional RCs.

## Later work

- investigate a safe direct B resume only if it can be implemented without synthetic/unverified input replay;
- longer dialogue/subtitle lifetime testing;
- in-engine cutscene coverage;
- repeated-cycle, load-transition, Alt-Tab, and controller-reconnect robustness;
- revalidate ABI facts when KCD2 changes from 1.5.6.

## Decision rule

> Reuse vanilla KCD2 pause ownership, suppress only the menu rendering, preserve exact presentation state, and prefer a visible vanilla-menu fallback over unverified resume tricks.
