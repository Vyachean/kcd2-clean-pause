# RC7d concrete-HUD Clean Pause — single-session retail test

This candidate builds only on behavior already established by retail tests. Do not spend launches re-checking individual hypotheses separately.

## Already established

On Xbox Store KCD2 1.5.6:

- vanilla pause acquisition through `Menu@0::IsVisible()` is reliable;
- suppressing only `Menu@0::Render()` produces a real paused state without drawing the pause menu;
- world simulation and audio stop like ordinary vanilla pause;
- second Escape/Start reveals the already-open vanilla pause menu without an unpause/re-pause cycle;
- strong vanilla pause depth-of-field blur is acceptable;
- vanilla pause hides HUD/subtitles;
- the rc7c global `SetHudElementsVisible(true)` approach alone did not restore them;
- `hud@0` resolves and the subtitle Flash-call hook can intercept `ClearSubtitles`.

## What rc7d changes

RC7d keeps KCD2 as the only pause owner and adds one concrete presentation intervention:

- hook generic `IUIElement::SetVisible`, but suppress `false` only for the verified `hud@0` object while pause acquisition/Clean Pause is active;
- explicitly enable the global HUD gate and set `hud@0` visible after vanilla pause opens;
- verify `hud@0::IsVisible() == true` before considering Clean Pause presentation valid;
- keep `ClearSubtitles` / `HideNarrativeSubtitles` suppression while Clean Pause owns presentation;
- all Menu visibility and all other UI visibility calls remain vanilla.

Physical Xbox B is still consumed by Clean Pause and uses the captured vanilla pause press/release route. That route remains unverified until an actual B test appears in the log.

## Install

1. Close KCD2.
2. Replace only `version.dll` beside the game executable with the asset from the `v0.1.0-rc.7d` GitHub prerelease.
3. Delete `kcd2_clean_pause_native.log` once before launch.

## One-session acceptance matrix

### A. Exploration — concrete HUD

1. In ordinary gameplay, choose a moment with any visible HUD/hint if convenient.
2. Press Start or Escape once.
3. Wait a couple of seconds.
4. Expected:
   - pause menu is not drawn;
   - world/audio are paused;
   - the HUD/hint that was visible immediately before pause remains visible;
   - background blur is allowed.

High-value log lines:

```text
hud@0 concrete visibility hook active
Clean Pause HUD preservation: suppressed hud@0 SetVisible(false)
Clean Pause HUD presentation verified: hud@0 visible=true
Clean Pause render suppression observed for Menu@0
```

The suppression line may be absent if this particular pause path did not issue a concrete hide call; the required visible result and `hud@0 visible=true` verification are what matter.

### B. Direct B resume

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
- vanilla HUD-hidden pause presentation is restored.

### D. Dialogue/subtitle — highest-value check

During a spoken line while its subtitle is visible:

1. press Start/Escape;
2. wait longer than the subtitle would normally remain;
3. expected:
   - the **same subtitle remains visible**;
   - speech/dialogue progression stays stopped;
   - audio remains paused;
   - no pause menu is drawn;
4. press Xbox B once;
5. expected: the same line continues without skip/cancel/duplicate and without showing the pause menu first.

### E. Cutscene if naturally available

If an in-engine cutscene occurs in the same session, repeat D once. Do not restart/reload solely to manufacture a cutscene test.

## Evidence to return

One fresh log plus four short results is enough:

- HUD/hints retained: yes/no;
- same subtitle retained: yes/no/not encountered;
- Xbox B resumes directly: yes/no/not tested;
- second Start/Escape shows vanilla menu: yes/no.

Do not perform an extra launch just because one optional case was unavailable.