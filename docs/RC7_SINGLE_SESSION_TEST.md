# RC7g borrowed-movieclip HUD snapshot — single-session retail test

Do not rerun rc7e or rc7f. RC7g is specifically built to preserve rc7e's visible-subtitle result while removing both unsafe pointer retention and rc7f's destructive `Release()` behavior.

## Already established

On Xbox Store KCD2 1.5.6:

- real vanilla pause ownership through `Menu@0` is reliable;
- suppressing only `Menu@0::Render()` hides the pause menu while world/audio remain paused;
- second Start/Escape can reveal the already-open vanilla pause menu continuously;
- root `hud@0` visibility alone is insufficient;
- the 28 HUD child movie clips are the relevant presentation layer;
- rc7e made the current subtitle visible during Clean Pause;
- rc7f crashed immediately on first pause after completing the gameplay child snapshot;
- rc7f's new immediate `Release()` of every `IUIElement::GetMovieClip()` result is rejected;
- Start=516, A=526, B=527 on the tested retail build.

## RC7g change

`IUIElement::GetMovieClip()` results are now treated as borrowed handles:

- never retained across helper calls;
- never stored in snapshot/global state;
- never `Release()`d;
- only the 28 visibility bools are stored.

RC7g also logs one first-entry/first-return pair for the `hud@0::Update` detour. If another crash occurs, the same log localizes it without a diagnostic retry.

## Install

1. Close KCD2.
2. Install only `version.dll` from `v0.1.0-rc.7g` beside the game executable.
3. Delete the previous `kcd2_clean_pause_native.log` once before launch.
4. Ensure the old `Documents\\kingdomcome_mods\\clean_pause` PAK is not active simultaneously.

## One-session sequence

### A. First-pause crash regression — mandatory first

1. Start normal gameplay.
2. Press Xbox Start once.
3. Wait 2–3 seconds.

Expected:

- **no crash**;
- ordinary pause menu is not drawn;
- world/audio are paused;
- subtitle/HUD that was already visible remains visible where applicable.

Expected useful markers include:

```text
HUD visibility snapshot captured for all 28 clips (gameplay-pre-pause)
hud@0 Update hook first entry ...
hud@0 Update original returned successfully
HUD visibility snapshot captured for all 28 clips (vanilla-pause)
Clean Pause gameplay HUD snapshot restored across all 28 clips
Running -> Clean Pause candidate: ...
Clean Pause render suppression observed for Menu@0
```

If it crashes, stop there. Do not repeat. Send the single fresh native log.

### B. rc7e visible-menu crash regression

If A succeeds:

1. while in Clean Pause, press Start again;
2. ordinary vanilla pause menu should appear;
3. press Xbox B once.

Expected:

- no crash;
- B behaves like ordinary vanilla pause Back/close;
- gameplay resumes normally.

### C. Direct B from Clean Pause

Enter Clean Pause again and press Xbox B directly without revealing Menu first.

Expected:

- gameplay resumes directly;
- no visible pause-menu flash;
- no dialogue cancel/cutscene skip side effect.

Useful markers:

```text
Clean Pause physical input: key=527 name=xi_b ...
B resume: replaying vanilla pause ...
Clean Pause -> running via B using replayed vanilla pause toggle
```

### D. Subtitle lifetime

If a spoken subtitle naturally occurs during the same session:

1. pause while that subtitle is visible;
2. wait longer than its normal lifetime;
3. confirm the same subtitle remains visible;
4. confirm speech/dialogue progression and audio remain paused;
5. direct B should continue the same line without skip/cancel/duplicate.

### E. Repeated cycles

Repeat both paths several times in the same session:

- Start -> Clean Pause -> Start -> visible menu -> B;
- Start -> Clean Pause -> direct B.

Optional only if naturally convenient: Alt-Tab, load transition, controller reconnect.

## Evidence to return

One log plus short results:

- first pause stable: yes/no;
- subtitle/HUD retained: yes/no/not encountered;
- visible-menu B stable: yes/no/not tested;
- direct B resumes: yes/no/not tested;
- subtitle survives long pause: yes/no/not encountered;
- repeated cycles stable: yes/no/not tested.

If anything fails or crashes, do not perform another launch.
