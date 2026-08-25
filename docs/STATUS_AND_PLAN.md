# Current status and plan

## Release status

**v0.2.0** is the current stable release target for KCD2 1.5.6 Windows retail.

Support status is per edition:

- **standalone `version.dll`: supported / retail-proven** on the primary PC Xbox Store / Xbox app target;
- **`KCD2CleanPause.asi`: experimental / not retail-validated**. It builds from the same runtime, but its loader path and coexistence with another ASI plugin have not been tested in retail.

The `0.2.0` feature set adds:

- standalone and ASI packaging from one runtime;
- process-wide duplicate-load protection;
- blur-free Clean Pause presentation with exact DoF-state restoration;
- preservation of active NPC speech bubbles / overhead subtitles across the vanilla pause transition.

The historical `v0.1.1-rc.1` through `v0.1.1-rc.4` tags remain immutable. No stable `v0.1.1` is planned; their accumulated feature work belongs to `v0.2.0`.

## Retail acceptance

On Xbox Store KCD2 1.5.6 using the standalone loading path, the accepted behavior is:

- Xbox Start enters the vanilla-owned Clean Pause without drawing the normal pause menu;
- simulation and audio pause normally;
- visible dialogue/HUD subtitles remain available;
- the retained frame is sharp without the vanilla pause DoF blur;
- NPC overhead subtitles are preserved together with the restored HUD;
- second Start or B reveals the already-open vanilla pause menu;
- closing the menu and resuming returns to normal game behavior.

The latest retail report confirms the pause works normally after the overhead-subtitle change. This closes the previous standalone blockers around normal handoff/resume behavior. No additional standalone retail launch is required for `v0.2.0`.

ASI acceptance is no longer a blocker for the stable standalone release. It remains an explicit prerequisite only before the ASI edition can be described as supported.

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

Direct `Clean Pause -> B -> Running` is not part of the current contract.

## Accepted runtime architecture

1. KCD2 is the sole pause owner.
2. The physical Escape/Start input is forwarded to KCD2.
3. `Menu@0::IsVisible()` is the pause-lifecycle signal.
4. Menu visibility is never changed by the mod; only `Menu@0::Render()` is suppressed during Clean Pause.
5. Gameplay and vanilla-pause HUD child visibility are preserved as boolean snapshots.
6. `IUIElement::GetMovieClip()` results are borrowed/call-local and are never retained or released by the mod.
7. `ClearSubtitles` and `HideNarrativeSubtitles` are narrowly suppressed while Clean Pause owns presentation.
8. `C_UIHudBubbles` is discovered from the live `hud@0` listener list through MSVC RTTI without fixed `WHGame.dll` RVAs.
9. `I_UIHudBubbles::UpdateBubbles()` and `ReleaseBubble()` are frozen only while vanilla pause is logically open.
10. `wh_cl_NearDof` and `r_DepthOfField` are captured, disabled for hidden-menu presentation, and restored before visible vanilla presentation.
11. Unresolved core state fails open to visible vanilla pause.

## Release model

The project uses SemVer and tag-driven GitHub Releases:

- features before 1.0 bump MINOR;
- fixes bump PATCH;
- `-rc.N` is used only when the supported release itself still requires acceptance;
- merges to `main` build and validate but do not publish;
- publication is triggered by an immutable matching `v<VERSION>` tag.

## Remaining work

The only edition-specific acceptance debt is ASI:

- run [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md) when a tester is available;
- verify one shared-loader coexistence case with another real KCD2 ASI plugin;
- after that, remove the experimental label from the ASI edition in a patch release if no runtime change is needed.

Non-blocking later work:

- investigate safe direct B resume only if a canonical vanilla close/resume mechanism is found;
- broader cutscene/dialogue coverage;
- repeated-cycle, load-transition, Alt-Tab, and controller-reconnect robustness;
- revalidate ABI facts when KCD2 changes from 1.5.6.

## Decision rule

> Reuse vanilla KCD2 pause ownership, suppress only the menu rendering, preserve exact presentation state, and prefer a visible vanilla-menu fallback over unverified resume tricks.
