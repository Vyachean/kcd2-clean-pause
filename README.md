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

Current prerelease candidate: **v0.1.0-rc.7f**.

Authoritative state:

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md)
- [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md)

## Accepted pause architecture

KCD2 itself remains the only pause owner.

1. Forward the physical Escape/Start event to vanilla KCD2.
2. Use `Menu@0::IsVisible()` as the retail-proven pause lifecycle signal.
3. Keep `Menu@0` logically visible.
4. Suppress only `Menu@0::Render()` while Clean Pause owns presentation.
5. Second Escape/Start restores Menu rendering and reveals the already-open vanilla menu without an unpause/re-pause cycle.

Retail testing confirms this pauses world simulation and audio correctly. Vanilla pause depth-of-field blur is accepted and out of scope.

## HUD/subtitle result

rc7c/rc7d proved that root `hud@0` visibility is not enough. KCD2's `C_UIHudMask` controls 28 named child movie clips inside the still-visible `hud` Flash movie.

rc7e switched to that child layer and produced the first positive HUD result: **the subtitle at the bottom of the screen remained visible during Clean Pause**.

The child-HUD mechanism is therefore retained.

## Why rc7e was rejected

rc7e crashed after:

1. Start -> Clean Pause with subtitle visible;
2. Start -> ordinary visible vanilla pause menu;
3. B -> crash.

A code audit found two lifecycle defects:

- rc7e retained 28 engine-owned `IFlashVariableObject*` wrappers across frames while render/input paths could use/release them concurrently;
- rc7e did not restore the exact vanilla-pause child HUD state before revealing the ordinary menu.

Do not rerun rc7e.

## rc7f — bool-only dual HUD snapshots

rc7f stores no engine-owned Flash pointer between calls.

Every child operation is:

```text
GetMovieClip(name)
  -> read or SetVisible
  -> Release()
```

The wrapper is released before the helper returns.

rc7f captures two exact visibility snapshots:

- **gameplay snapshot** before forwarding pause;
- **vanilla-pause snapshot** after real vanilla pause opens but before Clean Pause overrides child presentation.

Transitions then restore the corresponding state:

- Clean Pause -> gameplay snapshot;
- second Start/Escape -> vanilla-pause snapshot, then reveal Menu;
- direct B -> vanilla-pause snapshot, then replay the captured vanilla pause key;
- fail-open while paused -> best-effort vanilla-pause snapshot, then visible Menu.

`Menu::Render()` is presentation-only again. Bounded late HUD maintenance uses verified `hud@0::Update(float)` and refuses Flash mutation outside the validated main thread.

The narrow subtitle lifetime guard still suppresses only:

- `hud.ClearSubtitles`;
- `hud.HideNarrativeSubtitles`.

## Xbox input

Retail-proven values are explicit:

- Start = 516
- A = 526
- B = 527

Physical B is consumed while Clean Pause owns input and cannot leak into gameplay/dialog/cutscene actions.

## Key findings

- rc.1/rc.2: primary profile/action routing could lose Escape/Start — rejected.
- rc.4: inferred native pause ABI was wrong — rejected.
- rc.5: Lua/custom PauseGame does not reproduce full vanilla lifecycle — rejected for production.
- rc.6: `only_ui` is not vanilla pause ownership evidence.
- rc7b: `Menu@0` render suppression is the accepted pause/menu foundation.
- rc7c/rc7d: root HUD visibility is insufficient.
- rc7e: 28-child HUD presentation restored the visible subtitle, but its long-lived wrapper lifecycle is unsafe.
- rc7f: same proven child layer with call-local wrappers and separate gameplay/vanilla-pause snapshots.

## Verified interface ABI used by rc7f

- `IUIElement::Update(float)` = slot 23
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
- never retain `IFlashVariableObject*` child wrappers across calls/frames;
- never mutate HUD children from `Menu::Render()`;
- child Flash mutation only on the validated main thread;
- restore captured child visibility rather than force every child visible;
- physical B must not leak to gameplay/dialog/cutscene;
- unresolved state fails open to vanilla behavior.

## Distribution

**GitHub Releases are the canonical channel.** Candidate binaries are published as prereleases only after exact generated-source safety checks, MSVC x64 build, proxy/static-runtime validation, ZIP/checksum verification and exact-tag binding succeed.

For native candidates, remove the old `Documents\kingdomcome_mods\clean_pause` PAK before testing so only one implementation is active.

## Documentation

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md) — canonical state
- [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md) — rejected/superseded approaches
- [docs/RETAIL_EVIDENCE_RC7E.md](docs/RETAIL_EVIDENCE_RC7E.md) — subtitle success + crash evidence
- [docs/RC7_SINGLE_SESSION_TEST.md](docs/RC7_SINGLE_SESSION_TEST.md) — one-session rc7f acceptance matrix
- [docs/DESIGN.md](docs/DESIGN.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/RESEARCH.md](docs/RESEARCH.md)
- [docs/RELEASE.md](docs/RELEASE.md)
