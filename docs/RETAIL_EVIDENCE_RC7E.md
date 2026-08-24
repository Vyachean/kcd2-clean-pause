# RC7e retail evidence — subtitles restored, visible-menu exit crash

Source: user retail test on 2026-08-24 using `v0.1.0-rc.7e` on Xbox Store KCD2 1.5.6.

## User-visible result

RC7e produced the first confirmed HUD-presentation improvement:

- first pause entered Clean Pause without drawing the vanilla pause menu;
- **the subtitle at the bottom of the screen remained visible**;
- pressing Start a second time revealed the ordinary vanilla pause menu as intended.

The session then crashed after this exact sequence:

1. Start -> Clean Pause, Menu hidden, subtitles visible;
2. Start again -> ordinary visible vanilla pause menu;
3. B -> game crash.

No additional retail launch is required to establish these facts.

## What this proves

### The 28-child HUD layer is correct

RC7d had already proved that keeping `hud@0` itself visible was insufficient. RC7e switched to the 28 named child movie clips controlled by KCD2's HUD mask and the user immediately observed the subtitle again.

Therefore the child-clip presentation layer is now **retail-proven relevant**. Do not revert to root-HUD visibility experiments.

### RC7e is not safe enough to ship or continue testing

The crash occurred after leaving Clean Pause for the visible vanilla menu. A code audit found two concrete lifecycle defects in RC7e that make another run of the same binary unnecessary.

#### 1. Long-lived `IFlashVariableObject*` wrappers

RC7e stored 28 engine-owned `IFlashVariableObject*` wrappers in `g_hudClipSnapshot` across frames. `Menu@0::Render()` could use those wrappers while the input path for second Start called `ReleaseHudClipSnapshot()` and released all 28 wrappers.

That is an unsafe cross-thread lifetime: a render callback can already be inside HUD snapshot restoration when the input transition releases the same objects. This is a plausible use-after-free / heap-corruption source consistent with a crash that becomes visible on the next menu action.

Without a native crash stack this cannot be claimed as the exact faulting instruction, but it is independently a release-blocking bug and must be removed before another retail run.

#### 2. No exact vanilla-pause HUD restoration on second Start

RC7e restored the gameplay child visibility snapshot while Clean Pause was active. On second Start it stopped maintaining that snapshot and released the wrappers, but it did **not** restore the child visibility state that vanilla pause had established before Clean Pause overwrote it.

Thus the visible vanilla menu could inherit gameplay HUD child state until a later KCD2 refresh. B then closed a menu from a presentation state that was not the original vanilla pause state.

This is also a lifecycle correctness bug independently of the crash stack.

## RC7f correction

RC7f keeps the retail-proven 28-child idea but changes its ownership model:

- snapshots contain only 28 booleans; no engine pointer is retained between calls;
- every `GetMovieClip()` wrapper is acquired, used and `Release()`d within the same main-thread helper call;
- before pause: capture the gameplay HUD snapshot;
- after vanilla pause becomes active, but before overriding it: capture a second **vanilla-pause HUD snapshot**;
- Clean Pause restores the gameplay snapshot;
- second Start restores the exact vanilla-pause snapshot **before** revealing Menu;
- B restores the exact vanilla-pause snapshot before replaying the vanilla pause toggle;
- bounded late HUD maintenance moves out of `Menu::Render()` and into verified `hud@0::Update`, and refuses Flash mutation off the validated main thread;
- `Menu::Render()` returns to presentation-only suppression.

The narrow `ClearSubtitles` / `HideNarrativeSubtitles` guard remains because RC7e positively demonstrated visible subtitles.

## Test policy

Do not run RC7e again. The next retail launch, if RC7f passes all static/MSVC/release gates, should cover in one session:

- subtitle/HUD retention;
- second Start -> visible vanilla menu;
- B from visible vanilla menu (the crash scenario);
- direct B from Clean Pause;
- repeated pause cycles.
