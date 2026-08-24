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

Current prerelease candidate: **v0.1.0-rc.7d**.

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

## rc7d — dual HUD preservation

Vanilla pause also hides HUD/subtitles. rc7c proved that one `IFlashUI::SetHudElementsVisible(true)` call is insufficient even though `hud@0` resolves and `ClearSubtitles` can be intercepted.

rc7d therefore holds both known visibility layers while pause acquisition/Clean Pause is active:

- suppress `IFlashUI::SetHudElementsVisible(false)` for the verified FlashUI;
- suppress `IUIElement::SetVisible(false)` only for the verified `hud@0`;
- forward all `true` calls and all unrelated objects;
- explicitly enable the global HUD gate and set `hud@0` visible after vanilla pause acquisition;
- require `hud@0::IsVisible() == true` before accepting Clean Pause presentation ownership;
- suppress only `hud.ClearSubtitles` and `hud.HideNarrativeSubtitles` as a secondary subtitle-lifetime safeguard.

If HUD presentation cannot be verified, the candidate fails open to ordinary visible vanilla pause.

## B resume

Physical Xbox B is consumed while Clean Pause owns input so it cannot leak into `dialog_cancel`, `cutscene_skip`, or gameplay.

The candidate replays the exact physical pause press/release pair that opened vanilla pause through the original `PostInputEvent` route and accepts resume only if `Menu@0::IsVisible()` becomes false. Otherwise it fails open to ordinary visible vanilla pause.

This direct B route remains retail-unverified because the rc7c test log contained no physical B attempt.

## Key retail findings

- rc.1/rc.2: primary profile/action routing could lose Escape/Start — rejected.
- rc.3: official PAK/Lua/bootstrap/`consoleCMD` path works; tested `Game.PauseGame` binding unavailable.
- rc.4: inferred native pause ABI was wrong — rejected.
- rc.5: Lua/custom PauseGame does not reproduce the full audio/UI/subtitle lifecycle — rejected for production.
- rc.6: `only_ui` remains false even with visible vanilla pause — rejected as ownership evidence.
- writable-section `S_GameContext` scan prevented startup; fixed libKCD2 WHGame RVAs are storefront-dependent — rejected.
- rc7b: `Menu@0` render suppression is the accepted pause/menu foundation.
- rc7c: a one-shot global HUD enable is insufficient — rejected as a complete solution.
- rc7d: persistent global HUD hold + concrete `hud@0` hold is the active unverified presentation hypothesis.

## Safety constraints

Permanent rules include:

- no custom/inferred `PauseGame` production path;
- no `only_ui` ownership dependency;
- no action-map mutation or `Player.OnAction` replacement;
- no fixed libKCD2 WHGame RVAs for production lookup;
- never mutate `Menu@0` visibility;
- global HUD hook may suppress only `SetHudElementsVisible(false)` while pending/clean;
- concrete HUD hook may suppress only `hud@0::SetVisible(false)` while pending/clean;
- all other calls forward;
- unresolved runtime state fails open to vanilla behavior.

## Distribution

**GitHub Releases are the canonical channel.** Candidate binaries are published as prereleases after the generated-source safety gate, MSVC x64 build, proxy/static-runtime validation, ZIP/checksum verification, and exact-tag binding succeed.

Actions artifacts are CI evidence rather than the primary download surface.

For native candidates, remove the old `Documents\kingdomcome_mods\clean_pause` PAK before testing so only one implementation is active.

## Documentation

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md) — canonical current state and next gate
- [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md) — rejected/superseded approaches and evidence
- [docs/RC7_SINGLE_SESSION_TEST.md](docs/RC7_SINGLE_SESSION_TEST.md) — one-session retail acceptance matrix
- [docs/DESIGN.md](docs/DESIGN.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/RESEARCH.md](docs/RESEARCH.md)
- [docs/RELEASE.md](docs/RELEASE.md)
