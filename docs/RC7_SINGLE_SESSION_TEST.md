# RC7e HUD-child-snapshot Clean Pause — single-session retail test

This candidate builds only on behavior already established by retail tests. Do not spend launches re-checking individual hypotheses separately.

## Already established

On Xbox Store KCD2 1.5.6:

- vanilla pause acquisition through `Menu@0::IsVisible()` is reliable;
- suppressing only `Menu@0::Render()` produces a real paused state without drawing the pause menu;
- world simulation and audio stop like ordinary vanilla pause;
- second Escape/Start reveals the already-open vanilla pause menu without an unpause/re-pause cycle;
- strong vanilla pause depth-of-field blur is accepted;
- rc7c one-shot root HUD enable did not restore HUD/subtitles;
- rc7d persistent global + concrete `hud@0` root visibility also did not restore HUD/subtitles even with `hud@0::IsVisible()==true`;
- `hud@0` resolves and the subtitle Flash-call hook can intercept `ClearSubtitles`;
- the rc7d retail log proves Start=516, A=526 and B=527; the old contiguous enum used the wrong B value.

Static KCD2 1.5.6 analysis explains the missing HUD: `C_UIHudMask` controls 28 named child movie clips inside the still-visible `hud` Flash movie according to active UI sources.

## What rc7e changes

RC7e removes the rejected persistent root-HUD visibility hooks.

Before forwarding the physical pause press it:

1. resolves `hud@0`;
2. resolves all 28 verified child HUD movie clips;
3. reads each child's actual pre-pause display visibility;
4. stores that exact 28-value snapshot.

After vanilla pause opens it restores the captured bool for every child and briefly holds that snapshot through the existing Menu render transition for 750 ms so a late `C_UIHudMask` refresh cannot immediately erase it.

It does **not** force normally-hidden widgets visible.

The narrow subtitle lifetime guard remains and suppresses only:

- `hud.ClearSubtitles`;
- `hud.HideNarrativeSubtitles`.

Physical Xbox B now uses the retail-proven `KeyId::XiB = 527`. The captured vanilla pause-key replay route is otherwise unchanged and is being tested for the first valid time.

## Install

1. Close KCD2.
2. Open the GitHub prerelease `v0.1.0-rc.7e`.
3. Download `kcd2-clean-pause-v0.1.0-rc.7e.zip`.
4. Replace only `version.dll` beside the game executable.
5. Delete `kcd2_clean_pause_native.log` once before launch.
6. Make sure an old `Documents\\kingdomcome_mods\\clean_pause` PAK is not simultaneously active.

## One-session acceptance matrix

### A. Exploration — exact HUD retention

1. In ordinary gameplay, use a moment with a visible HUD element/contextual hint if convenient.
2. Press Start or Escape once.
3. Wait 2–3 seconds.
4. Expected:
   - pause menu is not drawn;
   - world/audio are paused;
   - UI that was visible immediately before pause remains visible;
   - UI that was hidden before pause does not suddenly appear;
   - background blur is allowed.

High-value log sequence:

```text
HUD child visibility snapshot captured for all 28 clips
Running -> Clean Pause candidate: ...
Clean Pause HUD child snapshot restored across all 28 clips
Clean Pause render suppression observed for Menu@0
```

If snapshot capture/restore fails, do not restart. The candidate should leave/show ordinary vanilla pause instead; send the same log.

### B. Direct Xbox B resume

While still in Clean Pause, press **Xbox B once**.

Expected:

- gameplay resumes immediately;
- ordinary pause menu does not appear first;
- no dialogue cancel/cutscene skip side effect occurs.

The critical log sequence is now:

```text
Clean Pause physical input: key=527 name=xi_b ...
B resume: replaying vanilla pause ...
Clean Pause -> running via B using replayed vanilla pause toggle
```

If `xi_b` is logged but the replay line is absent, that is a new code defect. If replay appears but resume fails, the same log distinguishes the replay timing/vanilla-close problem. Do not perform a second launch.

### C. Second pause key

Enter Clean Pause again and press Start/Escape a second time.

Expected:

- ordinary vanilla pause menu appears;
- gameplay remains continuously paused;
- normal vanilla HUD rules resume.

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

### E. Cutscene if naturally available

If an in-engine cutscene occurs in the same session, repeat D once. Do not restart/reload solely to manufacture a cutscene test.

### F. Repeated use

Use Clean Pause several more times during the same normal session. If convenient, include a load transition or Alt-Tab/controller reconnect. Do not create another game launch solely for optional robustness checks.

## Evidence to return

One fresh log plus four short results is enough:

- HUD/hints retained: yes/no;
- same subtitle retained: yes/no/not encountered;
- Xbox B resumes directly: yes/no/not tested;
- second Start/Escape shows vanilla menu: yes/no.

If anything fails, do not repeat the launch. This one session should distinguish the next failure class.
