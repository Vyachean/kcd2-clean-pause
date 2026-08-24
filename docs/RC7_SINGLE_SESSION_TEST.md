# RC7d dual-HUD Clean Pause — single-session retail test

This candidate builds only on behavior already established by retail tests. Do not spend launches re-checking individual hypotheses separately.

## Already established

On Xbox Store KCD2 1.5.6:

- vanilla pause acquisition through `Menu@0::IsVisible()` is reliable;
- suppressing only `Menu@0::Render()` produces a real paused state without drawing the pause menu;
- world simulation and audio stop like ordinary vanilla pause;
- second Escape/Start reveals the already-open vanilla pause menu without an unpause/re-pause cycle;
- strong vanilla pause depth-of-field blur is accepted;
- vanilla pause hides HUD/subtitles;
- rc7c proved that a one-shot `IFlashUI::SetHudElementsVisible(true)` alone does not restore visible HUD/subtitles;
- `hud@0` resolves and the subtitle Flash-call hook can intercept `ClearSubtitles`.

## What rc7d changes

RC7d keeps KCD2 as the only pause owner and holds both known HUD visibility layers during pause acquisition/Clean Pause:

1. **Global HUD gate**
   - hook `IFlashUI::SetHudElementsVisible` before forwarding the real pause event;
   - suppress only `SetHudElementsVisible(false)` for the verified FlashUI while pause acquisition/Clean Pause owns presentation;
   - all `true` calls forward.

2. **Concrete `hud@0` visibility**
   - hook generic `IUIElement::SetVisible` before forwarding pause;
   - suppress only `SetVisible(false)` where `this ==` the verified `hud@0` while pending/clean;
   - all `true` calls, all Menu calls, and all unrelated UI elements forward.

3. **Verified entry presentation**
   - after vanilla pause opens, explicitly enable the global HUD gate;
   - explicitly set `hud@0` visible;
   - require `hud@0::IsVisible() == true` before accepting Clean Pause presentation ownership.

4. **Subtitle lifetime safeguard**
   - suppress only `hud.ClearSubtitles` and `hud.HideNarrativeSubtitles` while pending/clean;
   - all other HUD Flash calls forward.

This does not resurrect the rejected rc7c hypothesis. rc7c tested a one-shot global enable as the complete solution; rc7d tests persistent global false-call suppression together with concrete HUD holding.

Physical Xbox B is consumed by Clean Pause and uses the captured vanilla pause press/release route. That route remains retail-unverified until an actual B attempt appears in the log.

## Install

1. Close KCD2.
2. Open the GitHub prerelease `v0.1.0-rc.7d`.
3. Download the canonical asset `kcd2-clean-pause-v0.1.0-rc.7d.zip`.
4. Replace only `version.dll` beside the game executable.
5. Delete `kcd2_clean_pause_native.log` once before launch.
6. Make sure an old `Documents\\kingdomcome_mods\\clean_pause` PAK is not simultaneously active.

## One-session acceptance matrix

### A. Exploration — HUD retention

1. In ordinary gameplay, choose a moment with a visible HUD element or contextual hint if convenient.
2. Press Start or Escape once.
3. Wait a couple of seconds.
4. Expected:
   - pause menu is not drawn;
   - world/audio are paused;
   - the HUD/hint visible immediately before pause remains visible;
   - background blur is allowed.

High-value log lines include:

```text
global HUD visibility hook active
hud@0 concrete visibility hook active
Clean Pause HUD presentation verified: hud@0 visible=true
Clean Pause render suppression observed for Menu@0
```

Depending on the exact pause path, either/both of these may also appear:

```text
Clean Pause HUD preservation: suppressed IFlashUI::SetHudElementsVisible(false)
Clean Pause HUD preservation: suppressed hud@0 SetVisible(false)
```

Their absence alone is not failure: vanilla may have hidden the HUD before/through another presentation mechanism. The user-visible HUD result and verified `hud@0 visible=true` line are the important evidence.

### B. Direct Xbox B resume

While still in Clean Pause, press **Xbox B once**.

Expected:

- gameplay resumes immediately;
- ordinary pause menu does not appear first;
- no dialogue cancel or cutscene skip side effect occurs.

Useful log sequence:

```text
Clean Pause physical input: ... xi_b ...
B resume: replaying vanilla pause ...
Clean Pause -> running via B using replayed vanilla pause toggle
```

If it fails, do not restart the game. The fail-open result should be the ordinary visible vanilla pause menu; send the same log.

### C. Second pause key

Enter Clean Pause again and press Start/Escape a second time.

Expected:

- ordinary vanilla pause menu appears;
- gameplay remains continuously paused;
- normal vanilla HUD-hidden pause presentation is restored.

### D. Dialogue/subtitle — highest-value check

During a spoken line while its subtitle is visible:

1. press Start/Escape;
2. wait longer than that subtitle would normally remain;
3. expected:
   - the **same subtitle remains visible**;
   - speech/dialogue progression stays stopped;
   - audio remains paused;
   - no pause menu is drawn;
4. press Xbox B once;
5. expected: the same line continues without skip/cancel/duplicate and without showing the pause menu first.

If the HUD remains visible but the subtitle still disappears, the log should distinguish a remaining subtitle-specific lifetime path from HUD visibility failure.

### E. Cutscene if naturally available

If an in-engine cutscene occurs in the same session, repeat D once. Do not restart/reload solely to manufacture a cutscene test.

### F. Repeated use

Use Clean Pause several more times during the same normal session. If convenient, include a load transition or Alt-Tab/controller reconnect. Do not create another game launch solely for these optional robustness checks.

## Evidence to return

One fresh log plus four short results is enough:

- HUD/hints retained: yes/no;
- same subtitle retained: yes/no/not encountered;
- Xbox B resumes directly: yes/no/not tested;
- second Start/Escape shows vanilla menu: yes/no.

If anything fails, do not repeat the launch. One session is intended to distinguish the next failure class.
