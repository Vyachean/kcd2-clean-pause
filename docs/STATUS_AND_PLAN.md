# Current status and plan

## Release status

**v0.2.0** is the current published stable release for KCD2 1.5.6 Windows retail.

Support status is per edition:

- **standalone `version.dll`: supported / retail-proven** on the primary PC Xbox Store / Xbox app target;
- **`KCD2CleanPause.asi`: experimental / not retail-validated**. It builds from the same runtime, but its loader path and coexistence with another ASI plugin have not been tested in retail.

The `0.2.0` feature set adds:

- standalone and ASI packaging from one runtime;
- process-wide duplicate-load protection;
- blur-free Clean Pause presentation with exact DoF-state restoration;
- preservation of active NPC speech bubbles / overhead subtitles across the vanilla pause transition.

The historical `v0.1.1-rc.1` through `v0.1.1-rc.4` tags remain immutable. No stable `v0.1.1` is planned; their accumulated feature work belongs to `v0.2.0`.

## Current unreleased work

Draft PR #34 addresses the visible `world freezes -> HUD disappears -> HUD returns` transition observed in `v0.2.0`.

The reviewed implementation observes KCD2's `C_UIHudMask` mutation path and restores only the gameplay Flash presentation in the same call stack while leaving KCD2's authoritative pause/HUD state untouched. A full-mod review additionally hardened this work by:

- preserving root `hud@0` visibility exactly instead of forcing HUD on;
- scoping both HUD-mask and NPC-bubble global MinHook detours to the concrete objects discovered from the current `hud@0`;
- using the previous complete authoritative vanilla HUD snapshot when a later internal-state read fails;
- logging mod version/build id and the loaded `WHGame.dll` PE fingerprint;
- pinning MinHook v1.3.4 to its immutable commit;
- including the required MinHook/HDE redistribution notice in both binary packages;
- validating the complete 17-export `version.dll` proxy surface.

PR #34 remains draft until one focused standalone retail run validates the corrected transition and normal Start/B menu handoff. If accepted, this work is a patch release target: **v0.2.1**.

## Retail acceptance

On Xbox Store KCD2 1.5.6 using the standalone loading path, the accepted `v0.2.0` behavior is:

- Xbox Start enters the vanilla-owned Clean Pause without drawing the normal pause menu;
- simulation and audio pause normally;
- visible dialogue/HUD subtitles remain available;
- the retained frame is sharp without the vanilla pause DoF blur;
- NPC overhead subtitles are preserved together with the restored HUD;
- second Start or B reveals the already-open vanilla pause menu;
- closing the menu and resuming returns to normal game behavior.

The latest stable retail report confirms normal pause/menu/resume behavior after the overhead-subtitle change. ASI acceptance is not a blocker for the supported standalone edition and remains an explicit prerequisite only before the ASI edition can be described as supported.

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
4. Menu visibility is never changed by the core Clean Pause state machine; only `Menu@0::Render()` is suppressed during Clean Pause.
5. Gameplay presentation snapshots preserve exact root `hud@0` visibility plus the 28 HUD-child visibility booleans.
6. The no-blink transaction reads authoritative vanilla child visibility from `I_UIHudMask::IsElementVisible` and never reconstructs a full vanilla state from a partial Flash mutation.
7. `IUIElement::GetMovieClip()` results are borrowed/call-local and are never retained or released by the mod.
8. `ClearSubtitles` and `HideNarrativeSubtitles` are narrowly suppressed while Clean Pause owns presentation.
9. `C_UIHudBubbles` is discovered from the live `hud@0` listener list through MSVC RTTI without fixed `WHGame.dll` RVAs.
10. Global HUD-mask/bubble method detours are scoped to the exact discovered runtime instances; unrelated class instances always forward to vanilla.
11. `I_UIHudBubbles::UpdateBubbles()` and `ReleaseBubble()` are frozen only for the target bubbles object while vanilla pause is logically open.
12. `wh_cl_NearDof` and `r_DepthOfField` are captured, disabled for hidden-menu presentation, and restored before visible vanilla presentation.
13. Unresolved core state fails open to visible vanilla pause.

## Release model

The project uses SemVer and immutable tag-backed GitHub Releases:

- features before 1.0 bump MINOR;
- fixes bump PATCH;
- `-rc.N` is used only when the supported release itself still requires acceptance;
- PR/main builds validate release-shaped artifacts without publishing from PRs;
- a release-preparation merge to `main` with a new `VERSION` automatically creates the matching immutable `v<VERSION>` tag and GitHub Release after the release build passes;
- an already-published release/tag is never moved or overwritten.

## Remaining work

Before PR #34 / v0.2.1:

- one focused standalone retail run for no-blink entry, second-Start menu handoff, B menu handoff, resume, HUD/DoF correctness;
- capture the newly logged Xbox Store KCD2 1.5.6 `WHGame.dll` fingerprint from that same run;
- promote that fingerprint into a strict compatibility gate in a later change only after the retail value is known and reviewed.

Edition-specific ASI acceptance debt remains:

- run [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md) when a tester is available;
- verify one shared-loader coexistence case with another real KCD2 ASI plugin;
- after that, remove the experimental label from the ASI edition in a patch release if no runtime change is needed.

Repository-maintenance debt found by the full review should be handled separately from PR #34: historical Lua/profile prototypes and diagnostic builders still live under canonical-looking `src/`, `mod/`, `vendor/`, and `tools/build.py` paths. They are not packaged by the current native release workflow, but should be quarantined/renamed so future contributors and agents cannot mistake rejected experimental paths for production.

Non-blocking later work:

- investigate safe direct B resume only if a canonical vanilla close/resume mechanism is found;
- broader cutscene/dialogue coverage;
- repeated-cycle, load-transition, Alt-Tab, and controller-reconnect robustness;
- document that ASI/native hooks are process-lifetime and hot DLL unload is unsupported;
- revalidate ABI facts when KCD2 changes from 1.5.6.

## Decision rule

> Reuse vanilla KCD2 pause ownership, suppress only the menu rendering, preserve exact presentation state, and prefer a visible vanilla-menu fallback over unverified resume tricks.
