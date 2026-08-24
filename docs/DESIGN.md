# Design

This document describes the **current production direction**. For the current stage, retail evidence, and decision tree, see [STATUS_AND_PLAN.md](STATUS_AND_PLAN.md).

## Product contract

Clean Pause must stop gameplay, dialogue and in-engine-cutscene progression while leaving the current rendered frame unobscured.

```text
Running
  Escape / Start -> CleanPaused

CleanPaused
  B              -> Running
  Escape / Start -> VanillaMenu
```

`VanillaMenu` is KCD2's real pause menu. Clean Pause never draws a replacement UI.

## Design principle

The current architecture does **not** create pause state itself.

KCD2 already has a pause path that owns all of the difficult coupled state:

- world/simulation pause;
- audio pause behavior;
- dialogue/cutscene suspension;
- pause counters/state;
- `only_ui` action-filter state;
- vanilla resume/menu behavior.

Clean Pause therefore reuses the vanilla pause lifecycle and changes only presentation:

> let vanilla KCD2 pause normally, verify that pause ownership exists, then hide only the visible pause-menu surface.

This replaces the older profile/Lua and inferred native `PauseGame` designs.

## Running -> hidden vanilla pause

For Escape or Xbox Menu / Start in an eligible gameplay context:

1. Perform read-only context checks before taking ownership of anything.
2. Forward the physical input event to KCD2 unchanged.
3. Verify that vanilla processing enabled `ActionMapManager` filter `only_ui`.
4. Resolve the retail pause-menu Flash element (`Menu@0`) through the verified KCD2 1.5.6 `IFlashUI` / `IUIElement` interfaces.
5. Call `IUIElement::SetVisible(false)` on that Menu element.
6. Verify the hidden state before the mod considers Clean Pause active.

The order is intentional:

```text
forward vanilla pause
  -> prove vanilla owns pause
  -> hide presentation
  -> only then isolate unrelated input
```

The mod must never reverse that ordering.

## Fail-open entry

Every runtime assumption is allowed to fail without breaking normal pause behavior.

If:

- context eligibility cannot be established;
- `only_ui` does not become active;
- `Menu@0` cannot be resolved;
- visibility cannot be changed or verified;

then Clean Pause does not acquire hidden-pause ownership. The already-forwarded vanilla event is left alone, so the user should receive the ordinary visible KCD2 pause menu.

A visible vanilla menu is the correct fallback.

## Input ownership while hidden

Unrelated gameplay/dialogue input may be consumed **only** after both conditions are proven:

1. vanilla `only_ui` pause is active;
2. the pause Menu element is hidden.

This prevents the rc.4 failure mode in which gameplay remained live while the mod swallowed input.

## B resume

B must use KCD2's own Back/Resume path.

While hidden:

1. reveal the vanilla Menu within the same input dispatch;
2. forward B to KCD2;
3. check `only_ui` again after vanilla handling;
4. if `only_ui` is gone, return to Running;
5. if vanilla remains paused, re-hide the Menu only after it is resolved and verified again.

The mod does not call a custom unpause primitive.

## Second Escape / Start

The second pause key should expose the ordinary KCD2 menu without changing pause ownership.

While hidden:

1. reveal the already-open Menu;
2. consume that second physical Escape/Start event;
3. leave vanilla pause state intact;
4. relinquish Clean Pause presentation ownership.

This avoids an `unpause -> open menu -> pause` transition and therefore avoids an intermediate simulation/audio tick.

## ABI boundary

The active implementation deliberately uses a narrow KCD2 1.5.6 ABI surface.

Currently relied upon facts:

```text
SSystemGlobalEnvironment + 0x98   -> IGame*
SSystemGlobalEnvironment + 0x140  -> IFlashUI*
IFlashUI::GetUIElementByInstanceStr -> slot 18
IUIElement::SetVisible              -> slot 28
IUIElement::IsVisible               -> slot 29
IInput::PostInputEvent              -> raw input hook before ActionMapManager
```

The `IGame*` distinction is important. rc.4 incorrectly treated `gEnv+0x98` as `IGameFramework*` and accidentally invoked `IGame::GetName()` through a PauseGame-shaped function pointer.

## Rejected pause mechanisms

### Full profile replacement / custom action-map ownership

Rejected after rc.1/rc.2 retail failures. It can remove the only vanilla pause path when a custom route fails and creates last-mod-wins compatibility problems around `defaultProfile.xml`.

### `Game.PauseGame`

rc.3 proved the Lua/console route worked but the tested Xbox Store runtime did not expose this binding.

### `CryAction.PauseGame` / `Action.PauseGame`

rc.5 retail testing showed a Lua pause route can freeze simulation but does not reproduce the complete vanilla pause lifecycle needed by Clean Pause. It is therefore diagnostic evidence, not the production mechanism.

### inferred native `IGameFramework::PauseGame`

Rejected after rc.4. The pointer source was wrong and the KCD2 slot/signature semantics were not proven. A call returning without an access violation is not evidence of pause acquisition.

## Permanent forbidden paths

- `ActionMapManager.InitActionMaps()`;
- runtime partial action-map reload as the primary Start interception mechanism;
- persistent controller remapping;
- `Player.OnAction` replacement;
- custom overlay/OCR;
- `Menu.gfx` replacement unless future retail evidence leaves no narrower presentation hook;
- any custom pause/input-swallow state entered without a verified vanilla pause.

## Current acceptance gates

The hidden-vanilla-pause design is accepted only if retail testing proves:

- first Escape and Start produce the full vanilla pause lifecycle;
- the visible pause menu is hidden without an unacceptable flash;
- current HUD/subtitle presentation remains usable;
- the same subtitle remains for the duration of Clean Pause;
- dialogue/cutscene audio and progression pause coherently;
- B resumes through vanilla behavior without skip/cancel leakage;
- second Escape/Start exposes the real vanilla menu without an intermediate unpause tick;
- repeated transitions never leave gameplay live with input swallowed.

See [TESTING.md](TESTING.md) for the current retail procedure.
