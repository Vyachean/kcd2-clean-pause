# v0.1.0-rc.7g — borrowed movieclip ownership correction

Prerelease candidate for Kingdom Come: Deliverance II 1.5.6 Windows retail, primarily Xbox Store / Xbox app.

## Why rc7g exists

RC7e proved that preserving KCD2's 28 HUD child movie clips can keep the current subtitle visible during Clean Pause.

RC7f then crashed immediately on the first pause. Its log reached a complete 28-child gameplay snapshot and `hud.ClearSubtitles` suppression, but never reached vanilla-pause snapshot capture or Clean Pause entry.

The key RC7f change at that point was immediate `Release()` of every `IUIElement::GetMovieClip()` result.

## Correct ownership model

RC7g treats `IUIElement::GetMovieClip()` results as borrowed/cached pointers:

- use only inside the current capture/restore helper call;
- never persist a movieclip pointer in global/snapshot state;
- never call `Release()` on `GetMovieClip()` results;
- keep only 28 visibility booleans in each snapshot.

This matches CryEngine's documented IUIElement usage, which does not require `Release()` for `GetMovieClip()`, while separately requiring Release for variable objects created through raw `IFlashPlayer` APIs.

## Existing lifecycle architecture retained

RC7g keeps the RC7f dual bool-only snapshots:

- gameplay HUD snapshot before forwarding physical pause;
- vanilla-pause HUD snapshot after KCD2 opens its real pause and before gameplay HUD restoration.

Transitions remain:

- Running -> Clean Pause: restore gameplay snapshot;
- second Start/Escape: restore vanilla-pause snapshot before revealing Menu;
- direct B: restore vanilla-pause snapshot before replaying vanilla pause toggle;
- fail-open while paused: best-effort vanilla-pause snapshot first.

`Menu@0::Render()` remains presentation-only.

## Update-hook diagnostics

The verified `IUIElement::Update(float)` slot 23 hook remains for bounded late HUD maintenance. RC7g adds one-shot markers before and after the original Update trampoline:

```text
hud@0 Update hook first entry ...
hud@0 Update original returned successfully
```

These markers add no recurring log spam and make any remaining crash self-localizing.

## Safety contract

Generated-source CI rejects:

- any `ReleaseFlashVariable` helper;
- any `kFlashVariableReleaseSlot` use in the candidate source;
- any `FlashVariableReleaseFn` use;
- any persisted `snapshot.clip` / `HudClipSnapshot` state;
- HUD child work from `Menu::Render()`;
- rejected PauseGame, `only_ui`, action-map, root-HUD and fixed-RVA paths.

CI requires:

- exactly 28 named HUD clips;
- call-local `void* clip{}` acquisition in capture and restore;
- no Release operation in either capture or restore;
- exact visibility bool replay;
- dual gameplay/vanilla-pause snapshots;
- main-thread-only periodic HUD mutation;
- direct-B vanilla replay route and nested-input protection.

## Retail gate

One session should first test:

1. first Start no longer crashes;
2. subtitle/HUD remains visible in Clean Pause;
3. second Start -> visible vanilla menu -> B remains stable;
4. direct B from Clean Pause resumes;
5. several repeated cycles remain stable.

If anything crashes, do not repeat the launch; return the single fresh native log.
