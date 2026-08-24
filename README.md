# KCD2 Clean Pause

Experimental **Kingdom Come: Deliverance II** mod targeting:

```text
Running
  Xbox Menu / Start -> Clean Pause
  Escape           -> Clean Pause

Clean Pause
  B                 -> Resume
  Xbox Menu / Start -> visible vanilla KCD2 pause menu
  Escape            -> visible vanilla KCD2 pause menu
```

The goal is to freeze gameplay, dialogue, in-engine cutscenes, audio and subtitle lifetime without covering the current rendered frame.

## Target

- KCD2 **1.5.6**
- Windows retail; PC Xbox Store / Xbox app / Game Pass is the primary tested storefront
- Xbox controller; Escape behaves analogously for pause/menu entry

Current prerelease candidate: **v0.1.0-rc.7d**.

For the authoritative status and evidence ledger, see:

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md)
- [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md)

## Current architecture

KCD2 itself remains the only pause owner.

1. The real physical Escape/Start event is forwarded to vanilla KCD2.
2. `Menu@0::IsVisible()` is used as the retail-proven signal that vanilla pause is active.
3. `Menu@0` remains logically visible; the mod never hides it with `SetVisible(false)`.
4. While Clean Pause owns presentation, only `Menu@0::Render()` is suppressed.
5. A second Escape/Start restores Menu rendering and reveals the already-open vanilla pause menu without an unpause/re-pause cycle.

Retail rc7b testing confirmed that this pauses world simulation and audio correctly while keeping the pause menu out of the rendered frame.

The strong depth-of-field blur from vanilla pause is accepted and is out of scope.

## rc7d — concrete HUD preservation

Vanilla pause also hides the game HUD/subtitles. rc7c proved that calling the global `IFlashUI::SetHudElementsVisible(true)` gate alone is insufficient even though `hud@0` resolves and its `ClearSubtitles` call can be intercepted.

rc7d therefore adds a narrow concrete-HUD intervention:

- hook the generic `IUIElement::SetVisible` implementation before forwarding the pause event;
- suppress `SetVisible(false)` only when `this` is the verified `hud@0` and pause acquisition/Clean Pause is active;
- forward all visibility calls for Menu and every other UI element unchanged;
- enable the global HUD gate and explicitly set `hud@0` visible after vanilla pause acquisition;
- require `hud@0::IsVisible() == true` before accepting Clean Pause presentation ownership;
- suppress only `hud.ClearSubtitles` and `hud.HideNarrativeSubtitles` as a secondary subtitle-lifetime safeguard.

If concrete HUD visibility cannot be verified, the candidate fails open to the ordinary visible vanilla pause menu.

## B resume

Physical Xbox B is consumed while Clean Pause owns input so it cannot leak into `dialog_cancel`, `cutscene_skip`, or gameplay.

The candidate records the exact physical pause press/release pair that opened vanilla pause. B replays that pair through the already-proven original `PostInputEvent` route and accepts resume only if `Menu@0::IsVisible()` becomes false. Otherwise it fails open to the ordinary visible vanilla pause menu.

This direct B route remains retail-unverified until a test session actually contains a physical Xbox B attempt.

## Key retail findings

- `rc.1` / `rc.2`: primary profile/action routing could lose Escape/Start — rejected.
- `rc.3`: official PAK/Lua/bootstrap/`consoleCMD` path works; tested `Game.PauseGame` binding unavailable.
- `rc.4`: invalid inferred native ABI; `gEnv+0x98` is `IGame*`, and guessed PauseGame ownership was false — rejected.
- `rc.5`: Lua/custom PauseGame freezes simulation but does not reproduce audio/UI/subtitle vanilla lifecycle — rejected for production.
- `rc.6`: `ActionMapManager.IsFilterEnabled("only_ui")` remains false even while the retail vanilla pause menu is visibly open — rejected as ownership signal.
- rejected menu-mode diagnostic: aggressive writable-section `S_GameContext` scanning prevented startup; fixed libKCD2 WHGame RVAs are storefront-dependent — rejected.
- `rc7b`: `Menu@0` render suppression is the accepted pause/menu foundation.
- `rc7c`: global HUD gate alone does not restore visible HUD/subtitles — rejected; concrete `hud@0` visibility is the rc7d target.

See [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md) for the detailed record.

## Verified ABI facts used by the candidate

For KCD2 1.5.6:

- `SSystemGlobalEnvironment + 0x98` = `IGame*`;
- `SSystemGlobalEnvironment + 0x140` = `IFlashUI*`;
- raw input hook = `IInput::PostInputEvent`;
- `IFlashUI::GetUIElementByInstanceStr` = slot 18;
- `IFlashUI::SetHudElementsVisible` = slot 28;
- `IUIElement::Render` = slot 24;
- `IUIElement::SetVisible` = slot 28;
- `IUIElement::IsVisible` = slot 29;
- named `IUIElement::CallFunction` = slot 69.

No inferred `IGameFramework::PauseGame` ABI is used.

## Safety constraints

Permanent rules include:

- never call `ActionMapManager.InitActionMaps()`;
- never reload a partial action-map profile as the primary pause mechanism;
- never persistently remap Start/B/Escape;
- never replace `Player.OnAction`;
- never use `CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, or an inferred native PauseGame ABI as the production pause owner;
- never use `only_ui` as pause ownership evidence;
- never mutate `Menu@0` visibility in the active architecture;
- never use fixed libKCD2 WHGame RVAs for production runtime lookup;
- rc7d may suppress `SetVisible(false)` only for the verified `hud@0`; every other call forwards;
- fail open to vanilla pause/input whenever a runtime assumption cannot be verified.

## Distribution

**GitHub Releases are the canonical channel.** Candidate binaries are not committed to the repository.

Retail-test candidates are published automatically as GitHub **prereleases** after:

1. static safety checks over the final generated C++;
2. Windows/MSVC x64 build;
3. version.dll proxy-export and static-runtime validation;
4. ZIP creation and SHA-256 verification.

The candidate workflow uses branch-level `cancel-in-progress` concurrency so an obsolete intermediate commit cannot publish after a newer candidate commit.

Each prerelease includes the candidate ZIP and `SHA256SUMS.txt` plus explicit known limitations.

For native candidates, remove the old `Documents\kingdomcome_mods\clean_pause` PAK before testing so only one implementation is active.

## Documentation

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md) — canonical current status and next gate
- [docs/REJECTED_HYPOTHESES.md](docs/REJECTED_HYPOTHESES.md) — rejected/superseded approaches and evidence
- [docs/RC7_SINGLE_SESSION_TEST.md](docs/RC7_SINGLE_SESSION_TEST.md) — current one-session retail acceptance matrix
- [docs/DESIGN.md](docs/DESIGN.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/RESEARCH.md](docs/RESEARCH.md)
- [docs/RELEASE.md](docs/RELEASE.md)
