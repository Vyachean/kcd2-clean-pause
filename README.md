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
- [docs/RETAIL_EVIDENCE_RC7F.md](docs/RETAIL_EVIDENCE_RC7F.md)

## Accepted pause architecture

KCD2 itself remains the only pause owner.

1. Forward the physical Escape/Start event to vanilla KCD2.
2. Use `Menu@0::IsVisible()` as the retail-proven pause lifecycle signal.
3. Keep `Menu@0` logically visible.
4. Suppress only `Menu@0::Render()` during Clean Pause.
5. Second Escape/Start reveals the already-open vanilla menu without an unpause/re-pause cycle.

Retail testing confirms world simulation and audio pause correctly. Vanilla pause depth-of-field blur is accepted.

## HUD/subtitle result

rc7c/rc7d proved that root `hud@0` visibility is insufficient. KCD2's HUD mask controls 28 child movie clips.

rc7e switched to that child layer and produced the first positive result: **the subtitle at the bottom remained visible during Clean Pause**.

The 28-child layer is therefore retained.

## rc7f crash and ownership correction

rc7f crashed immediately on the first pause. Its log reached:

- all three hooks installed;
- complete gameplay snapshot for all 28 children;
- `hud.ClearSubtitles` suppression;

but never reached vanilla-pause snapshot capture or Clean Pause entry.

The relevant rc7f change was immediate `Release()` of every `IUIElement::GetMovieClip()` result.

That ownership assumption is rejected. CryEngine's documented IUIElement usage treats `GetMovieClip()` as a directly usable returned pointer and separately requires caller `Release()` only for variable objects created through raw `IFlashPlayer` APIs. libKCD2 confirms `IFlashVariableObject::Release()` is destructive.

## rc7g

rc7g therefore treats `IUIElement::GetMovieClip()` results as **borrowed/cached handles**:

- use only inside the current capture/restore helper;
- never retain a movieclip pointer across calls or frames;
- never call `Release()` on it;
- store only the 28 visibility booleans.

This avoids both unsafe variants:

- rc7e retained raw pointers across frames;
- rc7f destructively released borrowed pointers.

The dual bool-only state remains:

- gameplay snapshot before physical pause;
- vanilla-pause snapshot after KCD2 opens pause but before gameplay HUD is restored;
- second Start restores vanilla-pause HUD before showing Menu;
- direct B restores vanilla-pause HUD before replaying the vanilla pause toggle.

`Menu::Render()` remains presentation-only.

## Additional crash localization

rc7g logs exactly one first-entry/first-return pair around the `hud@0::Update` trampoline:

```text
hud@0 Update hook first entry ...
hud@0 Update original returned successfully
```

If a crash remains, one log distinguishes the Update detour from child-snapshot ownership without a separate diagnostic build.

## Xbox input

Retail-proven ids:

- Start = 516
- A = 526
- B = 527

Physical B does not leak to gameplay/dialog/cutscene while Clean Pause owns input.

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
- [docs/RETAIL_EVIDENCE_RC7F.md](docs/RETAIL_EVIDENCE_RC7F.md)
- [docs/RC7_SINGLE_SESSION_TEST.md](docs/RC7_SINGLE_SESSION_TEST.md)
- [docs/RELEASE_RC7G.md](docs/RELEASE_RC7G.md)
