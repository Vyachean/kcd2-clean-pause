# RC7f race-free HUD snapshot — single-session retail test

Do **not** rerun rc7e. This test is designed to cover the rc7e crash regression and the remaining product gates in one session.

## Already established

On Xbox Store KCD2 1.5.6:

- vanilla pause acquisition through `Menu@0::IsVisible()` is reliable;
- suppressing only `Menu@0::Render()` produces a real paused state without drawing the pause menu;
- world simulation and audio stop like ordinary vanilla pause;
- second Escape/Start reveals the already-open vanilla pause menu without an unpause/re-pause cycle;
- strong vanilla pause depth-of-field blur is accepted;
- root `hud@0` visibility is not sufficient;
- KCD2's 28 child HUD clips are the relevant presentation layer;
- **rc7e restored the subtitle at the bottom of the screen during Clean Pause**;
- rc7e then crashed after Clean Pause -> second Start -> visible vanilla menu -> B;
- rc7e retained Flash wrappers across frames and did not restore an exact vanilla-pause child snapshot, so that binary is rejected;
- retail controller ids are Start=516, A=526, B=527.

## What rc7f changes

RC7f keeps the proven child-HUD result but changes lifecycle/ownership:

- snapshots store only 28 booleans;
- every `GetMovieClip()` wrapper is released before the helper returns;
- gameplay HUD is captured before pause;
- vanilla-pause HUD is captured after real pause opens and before gameplay HUD is restored;
- second Start restores vanilla-pause HUD before Menu is shown;
- direct B restores vanilla-pause HUD before replaying the vanilla pause toggle;
- `Menu::Render()` performs no HUD mutation or wrapper lifetime work;
- bounded HUD maintenance runs only from verified `hud@0::Update` on the validated main thread.

## Install

1. Close KCD2.
2. Open prerelease `v0.1.0-rc.7f`.
3. Download `kcd2-clean-pause-v0.1.0-rc.7f.zip`.
4. Replace only `version.dll` beside the game executable.
5. Delete `kcd2_clean_pause_native.log` once before launch.
6. Ensure an old `Documents\\kingdomcome_mods\\clean_pause` PAK is not active simultaneously.

## One-session acceptance matrix

### A. Subtitle/HUD retention

During normal gameplay, preferably while a subtitle or contextual HUD element is visible:

1. press Start once;
2. wait 2–3 seconds.

Expected:

- pause menu is not drawn;
- world/audio are paused;
- the subtitle/HUD that was visible immediately before pause remains visible;
- normally-hidden UI does not suddenly appear;
- background blur is allowed.

High-value log lines:

```text
HUD visibility snapshot captured for all 28 clips (gameplay-pre-pause)
HUD visibility snapshot captured for all 28 clips (vanilla-pause)
Clean Pause gameplay HUD snapshot restored across all 28 clips
Clean Pause render suppression observed for Menu@0
```

### B. Reproduce the rc7e crash sequence first

From Clean Pause:

1. press Start again;
2. confirm the ordinary vanilla pause menu appears;
3. press Xbox B once.

Expected:

- **no crash**;
- B closes the ordinary vanilla pause menu exactly as vanilla KCD2 normally does;
- gameplay resumes normally;
- HUD returns to normal gameplay state.

Useful log line before Menu appears:

```text
vanilla pause HUD snapshot restored before showing Menu
```

This is the highest-priority regression check because rc7e crashed on this sequence.

### C. Direct B from Clean Pause

Enter Clean Pause again, but this time press **Xbox B directly** without first revealing Menu.

Expected:

- gameplay resumes immediately;
- no visible menu flash;
- no dialogue cancel/cutscene skip side effect.

Critical log sequence:

```text
Clean Pause physical input: key=527 name=xi_b ...
B resume: replaying vanilla pause ...
Clean Pause -> running via B using replayed vanilla pause toggle
```

If replay appears but resume fails, do not restart. The same log is enough.

### D. Subtitle lifetime

If a spoken subtitle is naturally available in this same session:

1. pause while the subtitle is visible;
2. wait longer than its normal lifetime;
3. expected: the **same subtitle remains visible**, speech/dialogue progression stays stopped, and audio remains paused;
4. direct B should continue the same line without skip/cancel/duplicate.

### E. Repeated cycles

Repeat the following several times in the same session:

- Start -> Clean Pause -> Start -> visible menu -> B;
- Start -> Clean Pause -> direct B.

If convenient, include Alt-Tab or a normal load transition, but do not create a separate launch solely for optional robustness checks.

## Evidence to return

One fresh native log plus these short results is enough:

- subtitle/HUD retained in Clean Pause: yes/no;
- rc7e crash sequence stable: yes/no;
- direct B resumes: yes/no;
- same subtitle survives long pause: yes/no/not encountered;
- repeated cycles stable: yes/no.

If anything fails or crashes, do not rerun. One session is intended to distinguish the next failure class.
