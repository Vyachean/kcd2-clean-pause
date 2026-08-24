# RC7c HUD-preserving Clean Pause — single-session retail test

This candidate builds on retail-proven rc7b behavior. Do not spend launches re-checking already established facts unless they regress.

## Already established by rc7b

On Xbox Store KCD2 1.5.6:

- vanilla pause acquisition through `Menu@0::IsVisible()` is reliable;
- suppressing only `Menu@0::Render()` produces a real paused state without drawing the pause menu;
- world simulation and audio stop like ordinary vanilla pause;
- second Escape/Start can reveal the already-open vanilla pause menu without resuming first;
- vanilla pause applies strong depth-of-field blur; that is accepted for this mod;
- rc7b also showed the remaining defects: vanilla pause hides the HUD/subtitles, and physical B does not resume directly while Menu rendering is suppressed.

## RC7c changes

KCD2 remains the only pause owner. The candidate still contains no custom `PauseGame` call, no action-map mutation, no `only_ui` dependency, and no fixed reverse-engineered runtime RVA.

RC7c adds two narrow presentation/input adaptations:

1. **HUD/subtitle preservation**
   - after vanilla pause is verified, call KCD2's `IFlashUI::SetHudElementsVisible(true)`;
   - keep `Menu@0` logically open but suppress only its Render call;
   - on `hud@0`, suppress only Flash calls named `ClearSubtitles` and `HideNarrativeSubtitles` during the pause transition/Clean Pause;
   - all other HUD Flash calls are forwarded unchanged.

2. **Direct B resume**
   - physical Xbox B is consumed by Clean Pause and never forwarded as `dialog_cancel` / `cutscene_skip`;
   - the candidate records the exact physical Escape/Start press/release pair that opened vanilla pause;
   - B replays that same pause pair through the already-proven original `PostInputEvent` route;
   - resume is accepted only if `Menu@0::IsVisible()` becomes false;
   - if it cannot be verified, render suppression is removed and ordinary visible vanilla pause is shown (fail-open).

Second Escape/Start still reveals the ordinary already-open pause menu instead of resuming.

## Install

1. Close KCD2.
2. Replace only `version.dll` beside the game executable with this candidate.
3. Delete `kcd2_clean_pause_native.log` once before launch so the new session is easy to read.
4. Do not use the rejected rc6 `C_UIMenu` diagnostic.

## One-launch acceptance matrix

Use one normal gameplay session. No restart is required just to reach an optional test.

### A. Exploration — HUD and B

1. In ordinary gameplay, note a visible HUD element or contextual hint if available.
2. Press Xbox Start/Menu once.
3. Wait 2–3 seconds.
4. Expected:
   - pause menu is not drawn;
   - world and audio are paused;
   - existing HUD/hints remain visible;
   - strong background blur is acceptable.
5. Press B once.
6. Expected: gameplay resumes immediately **without first showing the pause menu**.

Useful log sequence:

```text
rc7c HUD-preserving render-suppression candidate active
hud@0 subtitle-preservation hook active
Running -> Clean Pause candidate
Clean Pause render suppression observed for Menu@0
B resume: replaying vanilla pause ...
Clean Pause -> running via B using replayed vanilla pause toggle
```

### B. Second pause-key behavior

1. Enter Clean Pause again.
2. Press Start a second time.
3. Expected: ordinary vanilla pause menu appears and gameplay stays continuously paused.
4. Close that ordinary menu normally with B.

Repeat with keyboard Escape if convenient. Escape should have the same Clean Pause / second-Escape behavior.

### C. Dialogue/subtitle — highest-value test

During a spoken line while its subtitle is visibly on screen:

1. Press Start or Escape.
2. Wait longer than the subtitle would normally remain on screen.
3. Expected:
   - **the same subtitle remains visible**;
   - speech/dialogue progression is stopped;
   - audio is paused like vanilla pause;
   - no pause menu is drawn.
4. Press B.
5. Expected: the same line continues normally without skip/cancel/duplicate and without showing the pause menu first.

The physical B must not reach `dialog_cancel` or cutscene-skip bindings.

### D. Cutscene if naturally available

If an in-engine cutscene occurs during the same session, repeat the subtitle/B test once. Do not restart or reload solely to manufacture this case.

## Fail-open expectations

If HUD restoration, Menu verification, or the B replay route cannot be verified, the candidate must prefer an ordinary visible vanilla pause menu over swallowed/lost input.

Stop testing only for a crash, input loss, or inability to recover with the ordinary menu. Do not relaunch merely to repeat a failed subcase; return the one fresh log.

## Evidence to return

One fresh `kcd2_clean_pause_native.log` plus a short note:

- HUD/hints remain during Clean Pause: yes/no;
- subtitle remains during dialogue Clean Pause: yes/no/not reached;
- B resumes directly without menu: yes/no;
- second Start/Escape shows ordinary menu: yes/no;
- dialogue/audio remain paused: yes/no/not reached;
- any skip/cancel, input loss, crash, or menu flash.
