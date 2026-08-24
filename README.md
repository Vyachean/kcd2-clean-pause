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
- PC Xbox Store / Xbox app / Game Pass
- Xbox controller; Escape behaves analogously for pause/menu entry

Current prerelease: **v0.1.0-rc.6**. Retail acceptance of the hidden-vanilla-pause architecture is the current gate.

For the authoritative current status, rejected approaches and next-step decision tree, see [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md).

## Retail findings

- `v0.1.0-rc.1` / `rc.2` broke normal Escape/Start routing and are obsolete.
- `rc.3` proved the official PAK/Lua/bootstrap/`consoleCMD` route works, but `Game.PauseGame` is unavailable in the tested retail runtime.
- `rc.4` used an invalid native ABI. KCD2 `gEnv+0x98` is `IGame*`, not `IGameFramework*`; rc.4 accidentally called `IGame::GetName()` as though it were PauseGame and then swallowed input.
- `rc.5` safely proved that a retail Lua `PauseGame` binding exists and freezes world simulation, but **does not implement the full vanilla pause lifecycle**: audio/UI continue, subtitles expire, and UI state can still react to input.

Therefore the mod no longer calls any explicit `PauseGame` primitive.

## Current architecture — vanilla pause, hidden Menu

The current candidate lets KCD2 create its own real pause and changes presentation only:

1. Escape/Start is checked only for gameplay eligibility.
2. The physical input is forwarded to KCD2 unchanged.
3. The mod verifies that vanilla KCD2 enabled the `only_ui` filter.
4. It resolves the retail `Menu@0` Flash element through verified KCD2 1.5.6 `IFlashUI`/`IUIElement` slots.
5. It calls only `IUIElement::SetVisible(false)` on that Menu element.

KCD2 therefore remains the sole owner of pause counters, audio state, dialogue/cutscene suspension and action filters.

While the verified vanilla pause is hidden:

- unrelated input is consumed so invisible menu/gameplay actions cannot fire;
- **B** temporarily reveals the Menu inside the same input dispatch and forwards B to vanilla Back; if KCD2 closes the pause, gameplay resumes;
- a second **Escape/Start** reveals the already-open vanilla pause menu and consumes that physical input, avoiding an intermediate unpause tick.

### Fail-open behavior

If any runtime assumption fails:

- if vanilla `only_ui` does not become active, nothing is hidden;
- if `Menu@0` cannot be found or hidden, the ordinary visible vanilla pause menu remains;
- hidden state is never entered merely because a function call did not crash.

## Verified ABI facts used

For KCD2 1.5.6:

- `SSystemGlobalEnvironment + 0x98` = `IGame*`;
- `SSystemGlobalEnvironment + 0x140` = `IFlashUI*`;
- `IFlashUI::GetUIElementByInstanceStr` = slot 18;
- `IUIElement::SetVisible` = slot 28;
- `IUIElement::IsVisible` = slot 29;
- input hook remains `IInput::PostInputEvent` before ActionMapManager.

No inferred `IGameFramework::PauseGame` ABI is used.

## Safety constraints

Permanent rules:

- never call `ActionMapManager.InitActionMaps()`;
- never reload a partial action-map profile at runtime;
- never persistently remap the controller;
- never replace `Player.OnAction`;
- never use `CryAction.PauseGame`, `Action.PauseGame`, `Game.PauseGame`, or an inferred native PauseGame ABI as the production pause mechanism;
- fail open to vanilla pause/input whenever a runtime assumption cannot be verified.

## Distribution

GitHub Releases are the canonical channel. Generated DLL/ZIP files are not committed.

```text
implementation PR
  -> Validate CI + Release build/package CI
  -> merge to main
  -> release PR changes VERSION
  -> CI
  -> merge to main
  -> GitHub Actions builds version.dll
  -> Linux job verifies the exact artifact
  -> GitHub Release + ZIP + SHA256SUMS.txt
```

For native candidates, remove the old `Documents\kingdomcome_mods\clean_pause` PAK before testing so only one implementation is active.

See:

- [docs/STATUS_AND_PLAN.md](docs/STATUS_AND_PLAN.md) — canonical current status and plan
- [docs/DESIGN.md](docs/DESIGN.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/RESEARCH.md](docs/RESEARCH.md)
- [docs/RELEASE.md](docs/RELEASE.md)
- [docs/RC5_DIAGNOSTIC.md](docs/RC5_DIAGNOSTIC.md) — historical rc.5 gate/results
