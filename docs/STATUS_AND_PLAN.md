# Current status and plan

This is the canonical project-status document. Historical prototype documents remain for context, but they must not override the decisions recorded here. Rejected hypotheses are tracked in `docs/REJECTED_HYPOTHESES.md`; retail-session evidence may be recorded in dedicated `RETAIL_EVIDENCE_*.md` files.

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

The strong depth-of-field blur applied by KCD2's vanilla pause is accepted and intentionally out of scope.

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

## Current candidate — v0.1.0-rc.7d

rc7d is the active functional candidate. It adds **concrete `hud@0` visibility preservation** to the accepted render-suppression foundation.

Before forwarding the physical pause event, rc7d installs a narrow hook on the generic `IUIElement::SetVisible` implementation. While vanilla pause acquisition is pending or Clean Pause is active it suppresses `SetVisible(false)` only when `this ==` the already-verified `hud@0` object. Every visibility call for Menu and every other UI element is forwarded unchanged.

After vanilla pause acquisition rc7d:

- enables the verified global HUD visibility gate;
- explicitly sets `hud@0` visible;
- requires `hud@0::IsVisible() == true` before accepting Clean Pause presentation ownership;
- keeps the two-name subtitle lifetime guard (`ClearSubtitles`, `HideNarrativeSubtitles`).

When switching to the ordinary visible vanilla pause menu, rc7d relinquishes Clean Pause first and restores the normal HUD-hidden vanilla pause presentation.

The candidate is built by CI and published as a GitHub prerelease after the safety contract, MSVC x64 build, proxy/static-runtime validation, and checksum validation succeed.

## State before rc7d retail acceptance

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

1. **Concrete HUD/subtitle retention must be tested in rc7d.** rc7c proved the global HUD gate alone is insufficient.
2. **Direct B resume is not yet retail-proven.** rc7c contains the route, but the supplied rc7c session log contains Escape interactions only; no physical B-resume attempt appears.
3. **Subtitle retention cannot be accepted until the current visible subtitle survives a real rc7d pause longer than its normal lifetime.**

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

The `IUIElement::SetVisible` ABI is not rejected globally: mutating **Menu** visibility is rejected because it destroys the independent pause lifecycle signal. rc7d uses the verified visibility API only for the concrete `hud@0` element, with strict object identity checks.

## B resume route

rc7d retains rc7c's captured-pause-key replay route:

- physical Xbox B is consumed while Clean Pause owns input;
- B is not forwarded to `dialog_cancel`, `cutscene_skip`, or gameplay;
- the exact physical pause press/release pair captured on entry is replayed through the already-proven original `PostInputEvent` route;
- resume is accepted only if `Menu@0::IsVisible()` becomes false;
- otherwise the candidate restores ordinary visible vanilla pause presentation and fails open.

This route remains **unverified**, not rejected, until retail evidence contains an actual physical B attempt.

## Release process

Every retail-test candidate from rc7 onward is published as a **GitHub prerelease immediately after CI succeeds**. Actions artifacts remain CI evidence but are not the primary distribution surface.

Candidate workflow requirements:

- branch-level `concurrency` with `cancel-in-progress` so an older candidate run cannot publish after a newer commit;
- static safety contract over the final generated C++;
- MSVC x64 build;
- version.dll proxy export validation;
- static MSVC runtime validation;
- ZIP + SHA-256 verification;
- prerelease notes with known limitations and the exact candidate tag.

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
- the rc7d SetVisible hook may suppress only `false` for the verified `hud@0`; all other calls must forward;
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