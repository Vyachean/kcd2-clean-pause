# Current status and plan

Canonical project status for KCD2 Clean Pause.

## Target UX

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  B              -> Running
  Escape / Start -> visible vanilla pause menu
```

Target: KCD2 1.5.6 Windows retail, primarily PC Xbox Store / Xbox app, Xbox controller first.

Clean Pause must preserve vanilla KCD2 pause ownership so gameplay, dialogue/cutscene progression, relevant audio and subtitle lifetime stop while the current game frame remains unobscured. Vanilla depth-of-field blur is accepted.

## Accepted pause foundation

Retail-proven:

- forward the real Escape/Start event to KCD2;
- use `Menu@0::IsVisible()` as the independent vanilla-pause lifecycle signal;
- never change `Menu@0` visibility;
- suppress only `Menu@0::Render()` while Clean Pause owns presentation;
- world simulation and audio pause correctly;
- second Start/Escape reveals the already-open vanilla menu without an unpause/re-pause tick;
- exiting from that visible vanilla menu is stable in rc7g;
- unresolved state fails open.

## Retail-proven HUD layer

rc7c/rc7d proved root HUD visibility is insufficient.

KCD2's `C_UIHudMask` controls 28 named child movie clips inside `hud@0`. rc7e preserved those children and produced the first confirmed positive result: the subtitle at the bottom remained visible during Clean Pause.

rc7g reconfirmed that result while also restoring first-pause and visible-menu stability.

Therefore the 28-child layer is accepted. Do not return to root-HUD visibility experiments.

## Historical regressions closed by rc7g

### rc7e

Worked far enough to show subtitles, but crashed after:

1. Start -> Clean Pause;
2. second Start -> visible vanilla menu;
3. B -> crash.

Its raw movieclip pointers were retained across frames, which remains rejected.

### rc7f

Crashed immediately on the first pause after a complete gameplay HUD snapshot. It introduced destructive `Release()` calls on `IUIElement::GetMovieClip()` results.

That ownership model remains rejected.

See `docs/RETAIL_EVIDENCE_RC7F.md`.

## Latest retail result — v0.1.0-rc.7g

The user confirmed this working sequence:

1. first pause -> Clean Pause without the vanilla pause menu;
2. subtitles remain visible;
3. second pause -> ordinary KCD2 pause menu appears;
4. pause can then be exited normally;
5. no crash occurs in this sequence.

This is the first retail-confirmed stable combination of hidden vanilla pause + preserved subtitle presentation + revealable vanilla menu + normal visible-menu exit.

See `docs/RETAIL_EVIDENCE_RC7G.md`.

## Accepted movieclip ownership rule

For `IUIElement::GetMovieClip()`:

- treat the returned pointer as borrowed/cached;
- use it only during the current helper call;
- never store it in global/snapshot state;
- never call `Release()` on it;
- store only visibility booleans.

This rule now has both static API support and positive rc7g retail evidence.

Rejected extremes remain:

- rc7e: raw movieclip pointers retained across frames;
- rc7f: borrowed movieclip pointers destructively released.

## Dual bool-only HUD snapshots

The accepted state model is:

1. capture gameplay child visibility before forwarding physical pause;
2. after real vanilla pause opens, capture vanilla-pause child visibility;
3. restore gameplay snapshot for Clean Pause;
4. on second Start/Escape restore vanilla-pause snapshot before revealing Menu;
5. on direct B restore vanilla-pause snapshot before replaying the vanilla pause toggle.

No child is blindly forced visible.

## HUD maintenance

`Menu@0::Render()` remains presentation-only.

Verified `IUIElement::Update(float)` slot 23 on resolved `hud@0` performs bounded late snapshot maintenance only while Clean Pause is active and only on the validated main thread.

RC7g also contains one-shot Update-trampoline markers for crash localization; the successful first-pause retail result means this hook no longer blocks the current architecture.

## Input facts

Retail-proven Xbox ids:

- Start = 516;
- A = 526;
- B = 527.

Physical B is consumed while Clean Pause owns input; it must not leak into gameplay/dialog/cutscene actions.

### Still unverified: direct B resume

The user has confirmed exiting after revealing the ordinary vanilla menu, but has not yet confirmed this distinct path:

```text
Clean Pause -> physical Xbox B -> Running
```

The captured pause-key replay mechanism therefore remains **unverified, not rejected**.

## Permanent rejected paths

Do not reintroduce without new direct evidence:

- profile/action-map routing as primary pause interception;
- action-map reload/remapping or `Player.OnAction` replacement;
- inferred/custom/Lua `PauseGame` production ownership;
- `only_ui` as vanilla pause evidence;
- `Menu@0::SetVisible(false)`;
- fixed storefront-dependent libKCD2 WHGame RVAs;
- aggressive writable-section `S_GameContext` scanning;
- root/global HUD visibility as complete child presentation;
- contiguous inferred XInput ids;
- raw `GetMovieClip()` pointers retained across frames;
- `Release()` on `IUIElement::GetMovieClip()` results;
- HUD child mutation from `Menu@0::Render()`.

## Active ABI facts

- `IFlashUI::GetUIElementByInstanceStr` = 18
- `IUIElement::Update(float)` = 23
- `IUIElement::Render()` = 24
- `IUIElement::SetVisible` = 28
- `IUIElement::IsVisible` = 29
- named `IUIElement::CallFunction` = 69
- `IUIElement::GetMovieClip(name)` = 71
- `IFlashVariableObject::GetDisplayInfo` = 26
- `IFlashVariableObject::SetVisible` = 33
- Xbox `XiStart=516`, `XiA=526`, `XiB=527`

`IFlashVariableObject::Release` exists at slot 0 but is not an ownership operation permitted on `IUIElement::GetMovieClip()` results.

## Remaining retail gates

Do not ask for a separate game launch solely for one of these. In the next naturally useful session, cover as many as possible:

1. direct B from Clean Pause should resume without visible menu flash/skip/cancel;
2. hold a spoken subtitle beyond its normal lifetime while paused;
3. confirm speech/dialogue progression remains stopped and resumes the same line;
4. if a cutscene occurs naturally, check the same behavior once;
5. repeat both Clean Pause -> visible menu -> exit and Clean Pause -> direct B several times.

## Stable release gate

Stable `v0.1.0` remains blocked until retail confirms:

- direct B resume;
- long-duration subtitle lifetime;
- dialogue/cutscene/audio pause coherence;
- repeated use stability;
- fail-open behavior;
- installation/uninstallation/proxy conflict documentation.

Already confirmed by rc7g:

- first pause stable;
- pause menu hidden on first pause;
- subtitle visible in Clean Pause;
- second Start reveals ordinary vanilla pause;
- exiting from visible vanilla pause is stable.

## Decision rule

> Reuse vanilla KCD2 pause ownership, preserve exact HUD child visibility as bool state, and treat `IUIElement::GetMovieClip()` pointers as call-local borrowed handles only.
