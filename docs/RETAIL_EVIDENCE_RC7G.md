# RC7g retail evidence — accepted v0.1.0 baseline

Source: Xbox Store KCD2 1.5.6 retail sessions on 2026-08-24.

## Confirmed user-visible behavior

The working sequence is:

1. press pause once -> Clean Pause opens without the vanilla pause menu;
2. subtitles remain visible at the bottom of the screen;
3. press pause a second time -> the ordinary KCD2 pause menu appears;
4. the visible menu can then be exited normally;
5. no crash occurs in this sequence.

A later check established one additional fact:

- pressing **Xbox B directly from Clean Pause reveals the ordinary vanilla pause menu** rather than resuming immediately.

The user explicitly accepted this behavior for v0.1.0.

## What this proves

RC7g closes both previous crash regressions:

- rc7e: crash after Clean Pause -> visible menu -> exit;
- rc7f: immediate crash on first pause.

It also confirms that KCD2's 28 child HUD movie clips are the relevant presentation layer for retaining the current subtitle during Clean Pause.

## Accepted movieclip ownership model

`IUIElement::GetMovieClip()` results are treated as borrowed/cached handles:

- use only inside the current helper call;
- do not persist pointers in global/snapshot state;
- do not call `Release()` on them;
- persist only child visibility booleans.

This model is supported by both API evidence and successful retail behavior.

## Accepted v0.1.0 input contract

Because direct B resume was never successfully proven and the menu-reveal behavior is acceptable, stable production deliberately removes the synthetic captured-Start/Escape replay experiment.

For v0.1.0:

```text
Clean Pause + B -> restore vanilla-pause HUD snapshot -> reveal vanilla Menu
```

Physical B is not forwarded into gameplay/dialogue/cutscene action maps while Clean Pause owns input.

## Remaining non-blocking validation

Long-duration subtitle lifetime, broader dialogue/cutscene coverage, repeated transitions, load/Alt-Tab, and controller reconnect are useful post-release robustness checks but are not required for the accepted v0.1.0 baseline.
