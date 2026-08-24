# KCD2 Clean Pause

Experimental **Kingdom Come: Deliverance II** mod targeting:

```text
Running
  Xbox Menu / Start -> Clean Pause
  Escape            -> Clean Pause

Clean Pause
  B                 -> Resume
  Xbox Menu / Start -> visible vanilla KCD2 pause menu
  Escape            -> visible vanilla KCD2 pause menu
```

The goal is to freeze gameplay, dialogue, in-engine cutscenes, audio, and subtitle lifetime without covering the current rendered frame.

## Target

- KCD2 **1.5.6**
- Windows retail; PC Xbox Store / Xbox app / Game Pass is the primary tested storefront
- Xbox controller; Escape behaves analogously for pause/menu entry

Current prerelease candidate: **v0.1.0-rc.7e**.

Authoritative project state:

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md)
- [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md)

## Accepted pause architecture

KCD2 itself remains the only pause owner.

1. Forward the physical Escape/Start event to vanilla KCD2.
2. Use `Menu@0::IsVisible()` as the retail-proven pause lifecycle signal.
3. Keep `Menu@0` logically visible.
4. Suppress only `Menu@0::Render()` while Clean Pause owns presentation.
5. Second Escape/Start restores Menu rendering and reveals the already-open vanilla menu without an unpause/re-pause cycle.

Retail rc7b testing confirmed this pauses world simulation and audio correctly. The strong vanilla pause depth-of-field blur is accepted and out of scope.

## rc7e — preserve the real HUD child state

rc7c/rc7d established that whole-HUD visibility is not the layer vanilla pause uses to remove gameplay HUD presentation:

- one-shot `IFlashUI::SetHudElementsVisible(true)` was insufficient;
- persistent global HUD holding plus `hud@0::SetVisible(false)` suppression was also insufficient;
- rc7d verified `hud@0::IsVisible()==true` while the user still saw no HUD.

KCD2 1.5.6 reverse engineering identifies the deeper mechanism: `C_UIHudMask` controls 28 named child movie clips inside the still-visible `hud` Flash movie according to active framework UI sources.

rc7e therefore removes the rejected root visibility hooks. Before forwarding pause it snapshots the actual visibility of all 28 children through verified Flash interfaces. Once vanilla pause is active, it restores the exact pre-pause bool for every child and briefly keeps that snapshot across late transition refreshes.

It never forces normally-hidden widgets visible.

The narrow subtitle-lifetime safeguard still blocks only:

- `hud.ClearSubtitles`;
- `hud.HideNarrativeSubtitles`.

## Xbox B resume

The rc7d retail log exposed a separate ABI bug. The old code incorrectly assumed XInput ids were contiguous and compiled B as 523. Retail KCD2 reports:

- Start = 516;
- A = 526;
- B = 527.

rc7e names only these directly evidenced ids. Physical B is consumed while Clean Pause owns input and now can actually enter the captured-pause-key replay route for the first valid test.

## Key retail findings

- rc.1/rc.2: primary profile/action routing could lose Escape/Start — rejected.
- rc.3: official PAK/Lua/bootstrap/`consoleCMD` path works; tested `Game.PauseGame` binding unavailable.
- rc.4: inferred native pause ABI was wrong — rejected.
- rc.5: Lua/custom PauseGame does not reproduce the full audio/UI/subtitle lifecycle — rejected for production.
- rc.6: `only_ui` remains false even with visible vanilla pause — rejected as ownership evidence.
- writable-section `S_GameContext` scan prevented startup; fixed libKCD2 WHGame RVAs are storefront-dependent — rejected.
- rc7b: `Menu@0` render suppression is the accepted pause/menu foundation.
- rc7c: one-shot root HUD enable is insufficient.
- rc7d: persistent root HUD visibility is still insufficient; `hud@0::IsVisible()` is not child-presentation proof.
- rc7d also proved the retail controller ids and explained why B never entered the replay branch.
- rc7e: active hypothesis is exact pre-pause visibility snapshot/restore of all 28 HUD child clips.

## Verified interface ABI used by rc7e

- `IUIElement::GetMovieClip(name)` = slot 71
- `IFlashVariableObject::Release` = slot 0
- `IFlashVariableObject::GetDisplayInfo` = slot 26
- `IFlashVariableObject::SetVisible` = slot 33

These are KCD2 1.5.6 interface slots, not fixed storefront-dependent WHGame RVAs.

## Safety constraints

Permanent rules include:

- no custom/inferred `PauseGame` production path;
- no `only_ui` ownership dependency;
- no action-map mutation or `Player.OnAction` replacement;
- no fixed libKCD2 WHGame RVAs for production lookup;
- never mutate `Menu@0` visibility;
- do not retain rejected rc7d root-HUD visibility hooks;
- preserve captured child visibility instead of forcing all HUD children visible;
- release retained Flash child wrappers whenever Clean Pause ownership ends;
- physical B must not leak to gameplay/dialog/cutscene while Clean Pause owns input;
- unresolved runtime state fails open to vanilla behavior.

## Distribution

**GitHub Releases are the canonical channel.** Candidate binaries are published as prereleases after the exact generated-source safety gate, MSVC x64 build, proxy/static-runtime validation, ZIP/checksum verification, and exact-tag binding succeed.

Actions artifacts are CI evidence rather than the primary download surface.

For native candidates, remove the old `Documents\kingdomcome_mods\clean_pause` PAK before testing so only one implementation is active.

## Documentation

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md) — canonical current state and next gate
- [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md) — rejected/superseded approaches and evidence
- [docs/RETAIL_EVIDENCE_RC7D.md](docs/RETAIL_EVIDENCE_RC7D.md) — latest retail evidence
- [docs/RC7_SINGLE_SESSION_TEST.md](docs/RC7_SINGLE_SESSION_TEST.md) — one-session retail acceptance matrix
- [docs/DESIGN.md](docs/DESIGN.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/RESEARCH.md](docs/RESEARCH.md)
- [docs/RELEASE.md](docs/RELEASE.md)
