# RC7g retail evidence — first stable child-HUD Clean Pause lifecycle

Source: Xbox Store KCD2 1.5.6 retail session on 2026-08-24 using `v0.1.0-rc.7g`.

## User-visible result

The user reported the following working sequence:

1. press pause once -> Clean Pause opens without the vanilla pause menu;
2. subtitles remain visible at the bottom of the screen;
3. press pause a second time -> the ordinary KCD2 pause menu appears;
4. pause can then be exited normally from the visible vanilla menu.

The game did not crash in this sequence.

## What this proves

RC7g closes the two regressions introduced by RC7e/RC7f:

- the RC7e `Clean Pause -> visible menu -> exit` crash is no longer reproduced;
- the RC7f immediate crash on the first pause is no longer reproduced.

It also reconfirms the positive RC7e HUD result:

- KCD2's 28 child HUD movie clips are the correct presentation layer for keeping the current subtitle visible during Clean Pause.

## Ownership conclusion accepted

The working RC7g implementation treats `IUIElement::GetMovieClip()` results as borrowed/cached handles:

- use only inside the current helper call;
- do not persist movieclip pointers in global/snapshot state;
- do not call `Release()` on them;
- retain only visibility booleans.

This model is now supported by both static API evidence and retail behavior.

The two rejected alternatives remain:

- RC7e: persist raw movieclip pointers across frames;
- RC7f: immediately `Release()` every `GetMovieClip()` result.

## Pause/menu lifecycle accepted

Retail now confirms the combined presentation lifecycle:

- real KCD2 vanilla pause owns simulation/audio state;
- `Menu@0::IsVisible()` remains the lifecycle signal;
- suppressing only `Menu@0::Render()` produces Clean Pause;
- gameplay HUD child visibility can be restored without destabilizing the first pause;
- a second Start/Escape can restore the captured vanilla-pause HUD state and reveal the existing menu;
- exiting from that visible menu is stable.

## Still unverified

The user's successful report does **not** yet establish the direct-resume path:

```text
Clean Pause -> physical Xbox B -> Running
```

That path replays the captured vanilla pause-key pair while consuming physical B. It remains an explicit retail gate rather than being inferred from the successful visible-menu exit.

Long-duration subtitle lifetime, dialogue/cutscene continuation semantics and repeated-cycle robustness also remain to be confirmed when naturally convenient in one session; they do not justify separate launches by themselves.
