# Current status and plan

This is the canonical project-status document. Historical prototype documents remain for context, but they must not override the decisions recorded here. Rejected hypotheses are tracked in `docs/REJECTED_HYPOTHESES.md` and retail-session evidence may be recorded in dedicated `RETAIL_EVIDENCE_*.md` files.

## Target

Primary target:

- Kingdom Come: Deliverance II 1.5.6;
- Windows retail, with PC Xbox Store / Xbox app / Game Pass as the primary storefront;
- Xbox controller, with keyboard Escape behaving analogously to Xbox Menu / Start.

Required product behavior:

```text
Running
  Escape / Start -> Clean Pause

Clean Pause
  B              -> Running
  Escape / Start -> visible vanilla pause menu
```

Clean Pause must stop gameplay, dialogue/in-engine-cutscene progression, relevant audio, and subtitle lifetime while keeping the current rendered frame unobscured. It must not draw a replacement overlay.

The strong depth-of-field blur applied by KCD2's vanilla pause is accepted and is intentionally out of scope.

## Current accepted architecture

KCD2 remains the **only pause owner**.

1. Forward the real physical Escape / Xbox Start event to vanilla KCD2.
2. Resolve `Menu@0` through `IFlashUI`.
3. Use `Menu@0::IsVisible()` as the independent retail-proven signal that the vanilla pause/menu lifecycle is active.
4. Leave `Menu@0` logically visible to KCD2.
5. Suppress only `Menu@0::Render()` while Clean Pause is active.
6. A second Escape/Start stops render suppression and reveals the already-open vanilla menu without an unpause/re-pause cycle.
7. Unrelated gameplay/dialog/cutscene input is consumed only while verified vanilla pause ownership is active.
8. Any unresolved condition fails open to ordinary visible vanilla pause behavior.

This foundation was proven repeatedly by rc7b and remained stable in rc7c.

## Current state — after rc7c retail test

### Proven working

On Xbox Store KCD2 1.5.6:

- native bootstrap and raw `IInput::PostInputEvent` hook work;
- `Menu@0` resolves reliably;
- `Menu@0::IsVisible()` tracks vanilla pause lifecycle correctly;
- suppressing only `Menu@0::Render()` produces a real Clean Pause;
- world simulation stops;
- audio pauses exactly as with ordinary vanilla pause;
- repeated Clean Pause entry works;
- second Escape/Start reveals the already-open vanilla pause menu while keeping pause continuous;
- `hud@0` resolves;
- the named HUD `CallFunction` hook works and can intercept `ClearSubtitles`.

### Still unresolved

1. **HUD / subtitles are still hidden during Clean Pause.**
   rc7c called the verified `IFlashUI::SetHudElementsVisible(true)` after pause acquisition and suppressed `hud.ClearSubtitles`, but the user observed no visible difference from rc7b. Therefore the global HUD visibility gate is insufficient.

2. **Direct B resume is not yet retail-proven.**
   rc7c contains a route that consumes physical Xbox B and replays the captured vanilla pause key pair through the original `PostInputEvent`, but the supplied rc7c session log contains Escape interactions only. No B-resume attempt appears in that log, so this mechanism remains unverified rather than accepted or rejected.

3. **Subtitle retention cannot be accepted until the concrete HUD presentation remains visible.**
   Blocking `ClearSubtitles` is only a secondary safeguard; it is not useful if the HUD element itself is hidden.

## Retail evidence ledger

### rc.1 / rc.2 — profile/action routing rejected

Retail tests could lose Escape/Xbox Start entirely. Primary pause ownership must not depend on replacing the vanilla action-map route. Runtime action-map reload, persistent remapping, full profile replacement, and `Player.OnAction` replacement remain forbidden production mechanisms.

### rc.3 — official PAK/Lua/bootstrap chain proven

The PAK, Lua bootstrap, `System.AddCCommand`, and profile `consoleCMD` path were proven on retail. `Game.PauseGame` was unavailable.

### rc.4 — inferred native PauseGame ABI rejected

`SSystemGlobalEnvironment + 0x98` is `IGame*`, not `IGameFramework*`. KCD2 `IGame` slot 13 is `GetName()` and returns `"kcd2"`. rc.4 called the wrong method through a guessed PauseGame-shaped ABI and then incorrectly treated "did not crash" as proof of pause ownership.

Permanent rule: never infer engine state from an unknown call merely returning.

### rc.5 — Lua/custom PauseGame rejected for production

The retail-safe Lua pause route freezes world simulation but does not reproduce the full vanilla lifecycle: audio/UI continue and subtitle lifetime is not preserved correctly. `CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, and inferred native PauseGame remain forbidden production pause owners.

### rc.6 — `only_ui` ownership signal rejected

Retail diagnostics showed `ActionMapManager.IsFilterEnabled("only_ui") == false` even while the ordinary pause menu was visibly open. At the same time `Menu@0` resolved and its visibility correctly tracked vanilla pause open/close.

Conclusion: `only_ui` is not a valid pause-ownership invariant on Xbox Store KCD2 1.5.6.

### rejected C_UIMenu/S_GameContext diagnostic

A later read-only diagnostic attempted aggressive writable-section scanning for game-context/menu ownership state and prevented normal startup. That startup mechanism is rejected. Fixed reverse-engineered WHGame RVAs are also rejected for production because Xbox Store retail addresses do not match the libKCD2 reference build.

### rc7b — render suppression foundation accepted

Retail test proved:

- vanilla pause acquisition via `Menu@0::IsVisible()`;
- real pause with world/audio stopped;
- pause menu invisible when only `Menu@0::Render()` is suppressed;
- second Escape/Start reveals ordinary vanilla pause without an unpause tick;
- vanilla pause also hides HUD/subtitles;
- forwarding physical B to the hidden menu does not provide the desired direct-resume UX.

### rc7c — global HUD gate hypothesis rejected

Retail test proved the rc7c HUD hook was installed and actually suppressed a `hud.ClearSubtitles` call, but the user saw no visible difference from rc7b. `IFlashUI::SetHudElementsVisible(true)` is therefore not sufficient by itself.

See `docs/RETAIL_EVIDENCE_RC7C.md` and `docs/REJECTED_HYPOTHESES.md`.

## Corrected KCD2 1.5.6 ABI facts in active use

- `SSystemGlobalEnvironment + 0x98` = `IGame*`;
- `SSystemGlobalEnvironment + 0x140` = `IFlashUI*`;
- `IInput::PostInputEvent` is the raw input route used by the candidate;
- `IFlashUI::GetUIElementByInstanceStr` = slot 18;
- `IFlashUI::SetHudElementsVisible` = slot 28;
- `IUIElement::Render` = slot 24;
- `IUIElement::SetVisible` = slot 28;
- `IUIElement::IsVisible` = slot 29;
- named `IUIElement::CallFunction` = slot 69.

The `IUIElement::SetVisible` ABI is not rejected globally: mutating **Menu** visibility is rejected because it destroys the independent pause lifecycle signal. The next candidate may use the verified visibility API specifically for the concrete `hud@0` element, with strict object identity checks.

## Next candidate — rc7d concrete HUD visibility

The next functional candidate builds directly on rc7c and is intended to answer the remaining presentation issue in one normal retail session.

### HUD presentation

Before forwarding the pause event, install a narrow hook on the concrete `hud@0` element's `SetVisible` implementation.

While a vanilla pause acquisition is pending or Clean Pause is active:

- suppress only `SetVisible(false)` calls where `this == verified hud@0`;
- forward `SetVisible(true)` and every visibility call for every other UI element;
- after vanilla pause acquisition, call the verified HUD global visibility gate and explicitly set `hud@0` visible;
- verify `hud@0::IsVisible() == true` before accepting Clean Pause presentation ownership;
- keep the existing narrow `ClearSubtitles` / `HideNarrativeSubtitles` suppression as a secondary subtitle-lifetime guard.

If concrete HUD visibility cannot be verified, remove menu render suppression and leave ordinary visible vanilla pause.

### B resume

Keep rc7c's captured-pause-key replay route, but continue treating it as unverified until a retail B attempt appears in the log. Physical B must never leak to `dialog_cancel`, `cutscene_skip`, or gameplay while Clean Pause owns input.

### Visible vanilla menu transition

On second Escape/Start:

- relinquish Clean Pause first;
- restore ordinary vanilla pause HUD-hidden presentation;
- restore Menu rendering;
- consume the second physical pause press so the menu stays open continuously.

## Release process

Every retail-test candidate from rc7 onward must be published as a **GitHub prerelease immediately after CI succeeds**. Actions artifacts remain useful for CI evidence but are not the primary distribution surface.

Each candidate release must include:

- the candidate ZIP (`version.dll` + test/install notes);
- SHA-256 checksum;
- explicit known limitations / unverified behavior;
- the exact commit used to build it.

Stable `v0.1.0` remains blocked until all required retail behavior passes.

## Safety invariants

Release blocking:

- never call `ActionMapManager.InitActionMaps()`;
- never replace `Player.OnAction`;
- never persistently remap Start/B/Escape;
- never depend on full `defaultProfile.xml` replacement for the active implementation;
- never call rejected inferred/custom PauseGame routes;
- never use `only_ui` as pause ownership evidence;
- never mutate `Menu@0` visibility in the active architecture;
- never use fixed libKCD2 WHGame RVAs as production runtime discovery;
- never swallow unrelated input unless verified vanilla pause ownership already exists;
- nested/synthetic input created during vanilla dispatch must be forwarded exactly once and never interpreted as another physical command;
- unresolved state must fail open to vanilla pause/input behavior.

## Retail test policy

Game launches are expensive. Do not request one launch per hypothesis.

Before producing a candidate:

1. close everything possible through reverse engineering, source review, static safety checks, and MSVC CI;
2. combine compatible remaining hypotheses into one fail-open functional candidate;
3. instrument that candidate so one retail session distinguishes the remaining failure classes;
4. request only a normal one-session acceptance matrix, with optional dialogue/cutscene checks if naturally available.

Do not request a restart solely to reach an optional test case.

## Stable release gate

Stable `v0.1.0` requires retail confirmation that:

- first Start/Escape produces Clean Pause without visible pause menu;
- existing HUD/hints remain visible;
- the current subtitle remains visible beyond its normal lifetime;
- dialogue/cutscene progression and audio stop coherently;
- B resumes directly without menu flash, skip, or cancel;
- second Start/Escape reveals ordinary vanilla pause continuously;
- repeated use, load transitions, Alt-Tab/controller reconnect do not produce persistent input loss;
- failure paths remain vanilla/fail-open;
- installation/uninstallation and proxy-DLL conflict behavior are documented.

## Decision rule

> Reuse vanilla KCD2 pause ownership and remove only the visual obstruction.

No custom pause primitive is considered unless new retail evidence proves the vanilla pause lifecycle itself cannot satisfy the product requirements and a separately verified engine API reproduces all required pause subsystems.