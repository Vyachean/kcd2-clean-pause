# RC7 render-suppression candidate — single-session retail test

This candidate is designed to maximize evidence from one KCD2 launch.

## What changed

The candidate keeps KCD2 as the only pause owner. It never calls a pause/unpause primitive and never changes action maps.

Unlike rc.6, it does **not** use `only_ui` and does **not** call `Menu@0::SetVisible(false)`.

Instead:

1. the real physical Escape/Xbox Start event is forwarded to KCD2;
2. the candidate observes `Menu@0::IsVisible()`;
3. once vanilla has made `Menu@0` visible, the candidate suppresses only that element's `IUIElement::Render()` call;
4. `Menu@0` remains logically visible to KCD2, so `IsVisible()` remains an independent vanilla-owned lifecycle signal;
5. B is forwarded to the still-live vanilla menu to resume;
6. second Escape/Start stops render suppression and consumes that physical pause event, revealing the already-open vanilla menu without unpause/re-pause.

Nested/synthetic `PostInputEvent` calls generated while KCD2 processes a physical event are always forwarded exactly once and are never interpreted as new Clean Pause commands.

## Safety / fail-open

The candidate must leave ordinary vanilla behavior if any prerequisite fails:

- `Menu@0` cannot be resolved;
- `Render`/`IsVisible` vtable slots cannot be validated;
- the render hook cannot be installed;
- Menu visibility cannot be verified;
- a hidden state reaches another physical event before at least one Menu render was actually suppressed.

The candidate contains no `PauseGame`, no `SetVisible`, no action-map mutation, and no fixed `libKCD2` runtime RVAs.

## Install

1. Close KCD2.
2. Replace only the Clean Pause `version.dll` beside the game executable with the candidate DLL.
3. Delete `kcd2_clean_pause_native.log` before launch so the result is unambiguous.
4. Do not install the failed `rc6-menu-mode-diagnostic` DLL again.

## One-launch test matrix

Do all feasible checks in the same game session.

### A. Startup/title

- Game reaches the title/front-end normally.
- Keyboard/controller/mouse remain normal.

Expected log eventually contains:

```text
rc7 render-suppression candidate active
```

No Clean Pause action should occur on the title screen.

### B. Exploration — first Start

While standing still in ordinary gameplay:

1. press Xbox Start/Menu once;
2. wait 2–3 seconds;
3. confirm the pause menu itself is not drawn and the current frame remains unobscured;
4. confirm world simulation is stopped;
5. confirm audio behaves like normal KCD2 pause;
6. press an unrelated D-pad direction once — it should do nothing;
7. press B to resume.

Expected log sequence includes:

```text
Menu@0 render hook active
Running -> Clean Pause candidate
Clean Pause render suppression observed for Menu@0
Clean Pause -> running via vanilla B/back
```

Hard failure: live gameplay with swallowed input, crash, or visible menu while the log claims render suppression was observed.

### C. Exploration — second Start behavior

1. enter Clean Pause again with Start;
2. after the clean frame is visible, press Start a second time;
3. the already-open ordinary vanilla pause menu should become visible;
4. gameplay must remain continuously paused;
5. close normally with B.

Expected log:

```text
Clean Pause -> visible vanilla pause menu (second Escape/Start consumed; Render restored)
```

### D. Escape parity

Repeat B and C using keyboard Escape. Escape should behave analogously to Xbox Start/Menu.

### E. Dialogue/subtitle — highest-value acceptance check

During a spoken dialogue line with an on-screen subtitle:

1. press Start or Escape while the subtitle is visible;
2. wait longer than that subtitle would normally remain on screen;
3. record whether the **same subtitle remains visible**;
4. record whether speech/dialogue progression is fully stopped;
5. record audio behavior;
6. press B and confirm the line resumes without skip/cancel/duplicate.

This result decides whether hidden vanilla menu presentation is sufficient or whether vanilla pause separately hides/expires HUD/subtitle presentation.

### F. In-engine cutscene if readily available

If a cutscene is available without a restart, repeat the dialogue test once. Do not restart the game solely to reach one.

### G. Robustness in the same session

If convenient, do one load transition and one Alt-Tab/controller reconnect, then use Start once more. Any failure must degrade to ordinary vanilla input/menu behavior.

## Evidence to return

Return one fresh `kcd2_clean_pause_native.log` plus a short note containing:

- first Start: clean frame yes/no;
- B resume yes/no;
- second Start shows vanilla menu yes/no;
- Escape parity yes/no;
- dialogue subtitle retained yes/no;
- dialogue/audio stopped yes/no;
- any menu flash or input loss.

One session is intended to answer the remaining major architectural questions.
