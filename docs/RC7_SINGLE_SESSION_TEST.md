# RC7g remaining retail gates — single-session test

Do not rerun rc7e or rc7f. RC7g has already passed the core pause/menu lifecycle on Xbox Store KCD2 1.5.6.

## Already established by rc7g

Retail-confirmed:

- first Start enters Clean Pause without crashing;
- ordinary pause menu is hidden;
- world/audio use the real vanilla pause lifecycle;
- current subtitle remains visible at the bottom;
- second Start reveals the already-open ordinary KCD2 pause menu;
- that visible menu can then be exited normally;
- the rc7e visible-menu crash and rc7f first-pause crash are not reproduced.

The active movieclip ownership rule is therefore accepted:

- `IUIElement::GetMovieClip()` returns a borrowed/cached handle for this path;
- use it only inside the current helper call;
- do not retain it;
- do not `Release()` it;
- snapshots store only visibility booleans.

## Remaining checks

Do not create a separate game launch for each item. Cover as many as naturally fit in one normal session.

### A. Direct B from Clean Pause — highest priority

1. Enter Clean Pause with Start.
2. Press Xbox **B directly**, without first revealing the pause menu.

Expected:

- gameplay resumes directly;
- no visible vanilla pause-menu flash;
- no dialogue cancel/cutscene skip side effect.

Useful log markers:

```text
Clean Pause physical input: key=527 name=xi_b ...
B resume: replaying vanilla pause ...
Clean Pause -> running via B using replayed vanilla pause toggle
```

If B instead reveals the menu, does nothing, skips/cancels something, or crashes, do not repeat the launch. Return the same native log.

### B. Subtitle lifetime

If a spoken subtitle naturally occurs:

1. pause while that subtitle is visible;
2. wait longer than its normal lifetime;
3. confirm the **same subtitle remains visible**;
4. confirm speech/dialogue progression and audio remain paused;
5. resume and verify the same line/state continues without skip/duplicate.

### C. Repeated cycles

In the same session, repeat both paths several times:

- Start -> Clean Pause -> Start -> visible menu -> normal exit;
- Start -> Clean Pause -> direct B.

Optional only if naturally convenient: Alt-Tab, load transition, controller reconnect.

### D. Cutscene

Only if an in-engine cutscene occurs naturally, test one Clean Pause cycle there. Do not restart/reload solely to manufacture this case.

## Evidence to return

One fresh log plus short results is enough:

- direct B resumes: yes/no/not tested;
- same subtitle survives long pause: yes/no/not encountered;
- dialogue resumes the same line/state: yes/no/not encountered;
- repeated cycles stable: yes/no/not tested;
- cutscene pause stable: yes/no/not encountered.

If anything fails or crashes, do not perform another launch.
