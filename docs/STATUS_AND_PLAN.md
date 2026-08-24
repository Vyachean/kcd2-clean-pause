# Current status and plan

This is the canonical project-status document. Detailed rejected/superseded hypotheses are kept in `docs/REJECTED_HYPOTHESES.md`; retail evidence is kept in `docs/RETAIL_EVIDENCE_*.md`.

## Target UX

Primary target:

- Kingdom Come: Deliverance II 1.5.6;
- Windows retail, primarily PC Xbox Store / Xbox app / Game Pass;
- Xbox controller, with keyboard Escape analogous to Xbox Menu / Start.

Required behavior:

```text
Running
  Escape / Start -> Clean Pause

Clean Pause
  B              -> Running
  Escape / Start -> visible vanilla pause menu
```

Clean Pause must stop gameplay, dialogue/in-engine-cutscene progression, relevant audio, and subtitle lifetime while leaving the current rendered frame unobscured. No replacement overlay.

The strong depth-of-field blur applied by KCD2's vanilla pause is accepted and out of scope.

## Accepted pause foundation

KCD2 remains the **only pause owner**.

1. Forward the real physical Escape / Xbox Start event to vanilla KCD2.
2. Resolve `Menu@0` through `IFlashUI`.
3. Use `Menu@0::IsVisible()` as the retail-proven vanilla pause lifecycle signal.
4. Never mutate Menu visibility while Clean Pause is active.
5. Suppress only `Menu@0::Render()` to remove the visible pause menu.
6. A second Escape/Start restores Menu rendering and reveals the already-open vanilla menu without an unpause/re-pause tick.
7. Consume unrelated gameplay/dialog/cutscene input only while verified vanilla pause ownership exists.
8. Any unresolved state fails open to ordinary visible vanilla pause/input behavior.

This foundation was proven by rc7b and remained stable through rc7c/rc7d/rc7e.

## Proven HUD presentation layer

RC7d proved that root-level HUD visibility is not enough: `hud@0::IsVisible()==true` while HUD/subtitles are still visually absent.

libKCD2 1.5.6 reverse engineering identifies `C_UIHudMask` as the deeper layer. It controls **28 named child movie clips** inside the still-visible `hud` Flash movie according to active framework UI sources.

RC7e switched to those child clips and produced the first positive retail result: **the subtitle at the bottom of the screen was visible during Clean Pause**.

Therefore:

- the 28-child HUD layer is now retail-proven relevant;
- do not return to global/root-HUD visibility experiments;
- the child-snapshot concept is retained, but the RC7e lifetime implementation is rejected as unsafe.

## Latest retail result — rc7e

User-visible sequence:

1. Start -> Clean Pause without visible pause menu;
2. subtitle remains visible at the bottom;
3. Start again -> ordinary visible vanilla pause menu;
4. B -> game crash.

No additional RC7e launch is useful.

A code audit found two release-blocking RC7e lifecycle defects:

### Long-lived Flash wrappers

RC7e retained 28 engine-owned `IFlashVariableObject*` wrappers across frames in the HUD snapshot. `Menu@0::Render()` could still be using them while the second-Start input transition called `Release()` on all wrappers.

This is an unsafe cross-thread lifetime and a plausible use-after-free/heap-corruption source. Without a native crash stack it is not claimed as the exact faulting instruction, but it is independently sufficient to reject RC7e.

### Visible-menu HUD state was not restored exactly

RC7e overwrote vanilla pause child visibility with the gameplay snapshot. On second Start it stopped maintaining the gameplay snapshot and freed wrappers, but did not restore the exact child state vanilla pause had established before the override.

Thus the visible vanilla menu could inherit non-vanilla child state before B closed it.

See `docs/RETAIL_EVIDENCE_RC7E.md`.

## Active candidate — v0.1.0-rc.7f

RC7f keeps the retail-proven 28-child presentation mechanism but removes long-lived engine pointer ownership and makes transitions symmetric.

### Two bool-only snapshots

RC7f stores only 28 visibility booleans per snapshot. It keeps **no `IFlashVariableObject*` between calls**.

It captures:

1. **gameplay HUD snapshot** immediately before the physical pause press is forwarded;
2. **vanilla-pause HUD snapshot** after KCD2 has opened the real pause, but before Clean Pause restores gameplay presentation.

Every child access follows this lifetime:

```text
GetMovieClip(name)
  -> read or SetVisible
  -> Release()
```

The fresh wrapper is released before the helper returns on both success and failure paths.

### Exact transitions

Running -> Clean Pause:

- capture gameplay snapshot;
- forward real pause input;
- verify vanilla pause through `Menu@0::IsVisible()`;
- capture vanilla-pause snapshot;
- restore gameplay snapshot;
- suppress Menu render.

Clean Pause -> second Start/Escape:

- restore vanilla-pause snapshot **before** dropping Menu render suppression;
- reveal the already-open ordinary vanilla menu.

Clean Pause -> B:

- restore vanilla-pause snapshot first;
- replay the captured vanilla pause-key pair;
- accept resume only if `Menu@0` closes;
- physical B never leaks into gameplay/dialog/cutscene actions.

Fail-open while Menu remains active:

- best-effort restore vanilla-pause snapshot first;
- show ordinary vanilla pause.

### Main-thread HUD maintenance

RC7e performed child mutation from `Menu::Render()`. RC7f forbids this.

`Menu::Render()` is presentation-only again: suppress hidden Menu or forward original render.

RC7f hooks verified `IUIElement::Update(float)` slot 23 for resolved `hud@0`:

- original Update always runs first;
- HUD child mutation is allowed only when `GetCurrentThreadId()` matches the validated KCD2 main-thread id;
- late transition refresh is bounded to the first 750 ms;
- refresh occurs at most every 75 ms, not every frame;
- unsafe/unverified maintenance fails open to visible vanilla pause.

### Subtitle lifetime safeguard

Keep the narrow named HUD `CallFunction` guard that suppresses only:

- `ClearSubtitles`;
- `HideNarrativeSubtitles`.

RC7e's visible subtitle is positive evidence that this presentation/lifetime combination is worth retaining.

## Proven retail facts

On Xbox Store KCD2 1.5.6:

- native bootstrap and raw `IInput::PostInputEvent` hook work;
- `Menu@0` resolves reliably;
- `Menu@0::IsVisible()` tracks vanilla pause open/close;
- suppressing only `Menu@0::Render()` creates a real hidden vanilla pause;
- world simulation stops;
- audio pauses like vanilla pause;
- second Escape/Start reveals the already-open vanilla menu continuously;
- `hud@0` resolves;
- named HUD `CallFunction` interception works;
- global/root HUD visibility alone is insufficient;
- the 28-child HUD layer can restore a visible subtitle in Clean Pause;
- Xbox retail ids are Start=516, A=526, B=527;
- RC7e's long-lived Flash-wrapper snapshot lifecycle is unsafe and must not be reused.

## Remaining retail gates

One normal RC7f session should cover all remaining high-value questions:

1. Do subtitles/HUD remain visible in Clean Pause?
2. Does second Start reveal ordinary vanilla pause normally?
3. Does B from that visible vanilla menu avoid the RC7e crash?
4. Does direct B from Clean Pause enter the replay route and resume without menu flash/skip/cancel?
5. Does the same subtitle remain visible beyond normal lifetime while speech/audio remain paused?
6. Do several repeated pause cycles remain stable?

Do not request separate launches for individual items. Do not rerun RC7e.

## Rejected/superseded mechanisms

Do not reintroduce without new retail evidence:

- rc.1/rc.2 profile/action routing as primary pause interception;
- runtime partial action-map reload, persistent remapping, or `Player.OnAction` replacement;
- rc.4 inferred native `PauseGame` ABI;
- `CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, or Lua/custom PauseGame as production pause owner;
- `ActionMapManager.IsFilterEnabled("only_ui")` as pause ownership evidence;
- mutating `Menu@0` visibility to hide the pause menu;
- fixed libKCD2 WHGame RVAs for storefront-independent production lookup;
- aggressive writable-section `S_GameContext` / `C_UIMenu` scanning;
- one-shot or persistent root-HUD visibility as complete HUD restoration;
- `hud@0::IsVisible()` as proof of child presentation;
- blocking `hud.ClearSubtitles` alone as complete subtitle restoration;
- forwarding physical B directly to hidden vanilla Menu;
- contiguous inferred XInput key ids;
- RC7e long-lived `IFlashVariableObject*` HUD snapshots;
- HUD child mutation from `Menu::Render()`.

## Active ABI facts

For KCD2 1.5.6:

- `SSystemGlobalEnvironment + 0x98` = `IGame*`;
- `SSystemGlobalEnvironment + 0x140` = `IFlashUI*`;
- `IInput::PostInputEvent` raw input route = slot 13;
- `IFlashUI::GetUIElementByInstanceStr` = slot 18;
- `IUIElement::Update(float)` = slot 23;
- `IUIElement::Render` = slot 24;
- `IUIElement::SetVisible` = slot 28;
- `IUIElement::IsVisible` = slot 29;
- named `IUIElement::CallFunction` = slot 69;
- `IUIElement::GetMovieClip(name)` = slot 71;
- `IFlashVariableObject::Release` = slot 0;
- `IFlashVariableObject::GetDisplayInfo` = slot 26;
- `IFlashVariableObject::SetVisible` = slot 33;
- retail `XiStart=516`, `XiA=526`, `XiB=527`.

Flash child slots are interface ABI from libKCD2 1.5.6, not fixed storefront-dependent WHGame RVAs.

## Safety invariants

Release blocking:

- never call rejected/custom `PauseGame` routes;
- never use `only_ui` as ownership evidence;
- never mutate `Menu@0` visibility;
- never use fixed libKCD2 WHGame RVAs for production discovery;
- never retain `IFlashVariableObject*` child wrappers across helper calls/frames;
- never perform child HUD acquisition/mutation/release from `Menu::Render()`;
- Flash child mutation must be on validated main thread;
- capture vanilla-pause HUD state before gameplay HUD is restored;
- restore vanilla-pause HUD before revealing Menu or replaying B;
- child snapshot must replay captured bools, not force all 28 visible;
- physical B must not leak into gameplay/dialog/cutscene;
- nested/synthetic input generated during vanilla dispatch must forward exactly once and must not be interpreted as physical input;
- unresolved state must fail open.

## Release process

GitHub Releases are the canonical binary distribution channel.

Every retail-test candidate is published as a GitHub **prerelease** only after:

1. generating the exact final C++ used for compilation;
2. running the static safety contract over that generated source and ABI header;
3. building x64 Release with MSVC/static runtime;
4. validating proxy exports/dependencies;
5. packaging ZIP + `SHA256SUMS.txt`;
6. verifying the CI artifact;
7. publishing/updating the prerelease;
8. binding the tag to the exact successful push SHA and verifying the remote tag.

## Retail-test policy

Game launches are expensive. Before asking for another launch:

1. close everything possible by source review/reverse engineering/CI;
2. combine compatible hypotheses into one fail-open candidate;
3. instrument one session to distinguish remaining failure classes;
4. publish a CI-green prerelease first;
5. never request a retry of a crashing/rejected binary when code/static evidence already identifies a blocker.

## Stable release gate

Stable `v0.1.0` remains blocked until retail confirms:

- first Start/Escape produces Clean Pause without pause menu;
- HUD/hints/subtitles remain visible as appropriate;
- current subtitle remains visible beyond normal lifetime;
- dialogue/cutscene progression and audio pause coherently;
- B resumes directly without menu flash/skip/cancel;
- second Start/Escape reveals ordinary vanilla pause continuously;
- B from visible vanilla pause is stable;
- repeated use/load transitions/Alt-Tab/controller reconnect do not cause persistent input loss;
- all failure paths remain fail-open;
- installation/uninstallation and proxy-DLL conflict behavior are documented.

## Decision rule

> Reuse vanilla KCD2 pause ownership, preserve exact gameplay and vanilla-pause HUD child states, and keep engine-owned Flash wrappers strictly call-local.
