# v0.1.0-rc.7f — race-free HUD snapshot lifecycle

Prerelease candidate for Kingdom Come: Deliverance II 1.5.6 Windows retail, primarily PC Xbox Store / Xbox app.

## Why rc7f exists

RC7e achieved the first confirmed subtitle restoration in Clean Pause, proving the 28 child HUD movie clips are the correct presentation layer.

However, RC7e also crashed after:

1. Start -> Clean Pause with subtitles visible;
2. Start -> ordinary visible vanilla pause menu;
3. B -> crash.

A code audit found two release-blocking lifecycle bugs in RC7e:

- it retained 28 engine-owned `IFlashVariableObject*` wrappers across frames while render/input paths could use/release them concurrently;
- it did not restore the exact vanilla-pause child HUD state before revealing the ordinary menu.

RC7f removes both issues without discarding the retail-proven child-HUD mechanism.

## Pointer lifetime change

RC7f snapshots contain only 28 visibility booleans.

For every child operation:

1. `hud@0::GetMovieClip(name)` returns a fresh engine wrapper;
2. the wrapper is read or updated;
3. `Release()` is called before the helper returns.

No `IFlashVariableObject*` is retained across frames, input transitions or render callbacks.

## Dual HUD snapshots

RC7f captures two exact states:

- **gameplay snapshot** — immediately before forwarding the physical pause press;
- **vanilla-pause snapshot** — after KCD2 has opened its real pause, but before Clean Pause restores gameplay HUD presentation.

Transitions are therefore exact:

- Running -> Clean Pause: restore gameplay snapshot;
- Clean Pause -> second Start/Escape: restore vanilla-pause snapshot, then reveal Menu;
- Clean Pause -> B: restore vanilla-pause snapshot, then replay the vanilla pause toggle;
- fail-open while Menu remains active: best-effort restore vanilla-pause snapshot first.

No widget visibility is guessed or forced globally.

## Main-thread HUD maintenance

RC7e reapplied child state from `Menu::Render()`. RC7f removes all HUD mutation from that render hook.

Instead it hooks verified `IUIElement::Update(float)` slot 23 for the resolved `hud@0` element:

- original Update always runs first;
- HUD mutation is allowed only when `GetCurrentThreadId()` matches the validated KCD2 main-thread id;
- the gameplay snapshot is refreshed at most every 75 ms and only during the first 750 ms after Clean Pause entry;
- if maintenance cannot be performed safely, the candidate fails open to visible vanilla pause.

`Menu::Render()` is again presentation-only: it either suppresses the hidden Menu or forwards the original render.

## Subtitle lifetime safeguard

The narrow Flash call guard remains because RC7e showed visible subtitles:

- suppress `ClearSubtitles`;
- suppress `HideNarrativeSubtitles`;
- forward every other HUD Flash call.

## Xbox input

Retail-proven ids remain explicit:

- Start = 516;
- A = 526;
- B = 527.

Physical B is consumed while Clean Pause owns input and does not leak into gameplay/dialog/cutscene actions.

## Safety invariants

RC7f CI rejects generated source containing:

- long-lived `HudClipSnapshot` / `snapshot.clip` state;
- HUD child work inside `Menu::Render()`;
- rejected root-HUD visibility hooks;
- custom/inferred `PauseGame`;
- `only_ui` ownership checks;
- fixed storefront-dependent WHGame RVAs;
- action-map mutation.

CI additionally verifies:

- all 28 HUD child names are present;
- capture/restore release fresh wrappers on success and failure;
- vanilla-pause snapshot is captured before gameplay HUD is restored;
- second Start restores vanilla-pause HUD before revealing Menu;
- B restores vanilla-pause HUD before replay;
- HUD maintenance checks the validated main thread.

## One-session retail gate

After CI/release is green, one normal session should cover:

1. subtitles/HUD visible in Clean Pause;
2. second Start shows ordinary vanilla menu;
3. B from that visible menu does not crash;
4. direct B from Clean Pause resumes without menu flash/skip/cancel;
5. repeated cycles remain stable.

Do not rerun RC7e.
