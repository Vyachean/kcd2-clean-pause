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

Target: KCD2 **1.5.6**, Windows retail, primarily PC Xbox Store / Xbox app / Game Pass, Xbox controller first.

Current prerelease candidate: **v0.1.0-rc.7g**.

Authoritative state:

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md)
- [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md)
- [docs/RETAIL_EVIDENCE_RC7G.md](docs/RETAIL_EVIDENCE_RC7G.md)

## Retail-confirmed core behavior

On Xbox Store KCD2 1.5.6, rc7g now confirms:

1. first Start/Escape enters Clean Pause without drawing the vanilla pause menu;
2. the current subtitle remains visible at the bottom;
3. world simulation and audio use the real vanilla pause lifecycle;
4. second Start/Escape reveals the already-open ordinary KCD2 pause menu;
5. that visible menu can then be exited normally without the rc7e/rc7f crashes.

Vanilla pause depth-of-field blur remains accepted and out of scope.

## Accepted pause architecture

KCD2 itself remains the only pause owner.

1. Forward the physical Escape/Start event to vanilla KCD2.
2. Use `Menu@0::IsVisible()` as the retail-proven pause lifecycle signal.
3. Keep `Menu@0` logically visible.
4. Suppress only `Menu@0::Render()` during Clean Pause.
5. Second Escape/Start restores captured vanilla-pause HUD presentation and reveals the already-open menu without an unpause/re-pause cycle.

## HUD/subtitle presentation

Root `hud@0` visibility is insufficient. KCD2's HUD mask controls 28 child movie clips.

The active implementation captures exact child visibility booleans:

- gameplay snapshot before physical pause;
- vanilla-pause snapshot after KCD2 opens pause;
- Clean Pause restores gameplay visibility;
- second Start restores vanilla-pause visibility before revealing Menu.

rc7e first proved this child layer can keep subtitles visible; rc7g reconfirmed it with a stable core lifecycle.

## Movieclip ownership

Two unsafe alternatives are permanently rejected:

- rc7e retained raw `GetMovieClip()` pointers across frames;
- rc7f immediately called destructive `Release()` on every `GetMovieClip()` result and crashed on first pause.

rc7g uses the retail-validated model:

- `IUIElement::GetMovieClip()` result is a borrowed/cached handle;
- use it only inside the current helper call;
- never retain it across calls/frames;
- never call `Release()` on it;
- persist only visibility booleans.

## Xbox input

Retail-proven ids:

- Start = 516
- A = 526
- B = 527

Physical B does not leak to gameplay/dialog/cutscene while Clean Pause owns input.

### Remaining input gate

Direct resume from Clean Pause itself is still not retail-confirmed:

```text
Clean Pause -> Xbox B -> Running
```

That path restores the captured vanilla-pause HUD snapshot and replays the captured vanilla pause-key pair. It remains unverified rather than rejected.

## Safety constraints

- no custom/inferred `PauseGame` production path;
- no `only_ui` ownership dependency;
- no action-map mutation or `Player.OnAction` replacement;
- no fixed libKCD2 WHGame RVAs;
- never mutate `Menu@0` visibility;
- never retain `GetMovieClip()` pointers across helper calls;
- never call `Release()` on `IUIElement::GetMovieClip()` results;
- never mutate HUD children from `Menu::Render()`;
- child mutation only on validated main thread;
- preserve captured visibility instead of forcing all children visible;
- unresolved runtime state fails open.

## Distribution

**GitHub Releases are canonical.** Candidate binaries are published as prereleases only after generated-source safety checks, MSVC x64 build, proxy/static-runtime validation, ZIP/checksum verification and exact-tag binding succeed.

For native candidates, remove the old `Documents\kingdomcome_mods\clean_pause` PAK before testing so only one implementation is active.

## Documentation

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md)
- [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md)
- [docs/RETAIL_EVIDENCE_RC7G.md](docs/RETAIL_EVIDENCE_RC7G.md)
- [docs/RETAIL_EVIDENCE_RC7F.md](docs/RETAIL_EVIDENCE_RC7F.md)
- [docs/RC7_SINGLE_SESSION_TEST.md](docs/RC7_SINGLE_SESSION_TEST.md)
- [docs/RELEASE_RC7G.md](docs/RELEASE_RC7G.md)
