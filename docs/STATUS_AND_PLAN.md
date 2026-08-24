# Current status and plan

This is the canonical project-status document. Historical prototype documents remain for context, but they must not override the decisions recorded here.

## Target

Primary target:

- Kingdom Come: Deliverance II 1.5.6;
- PC Xbox Store / Xbox app / Game Pass;
- Xbox controller, with Escape behaving analogously to Xbox Menu / Start.

Product behavior:

```text
Running
  Escape / Start -> Clean Pause

Clean Pause
  B              -> Running
  Escape / Start -> visible vanilla pause menu
```

Clean Pause must stop gameplay, dialogue/in-engine-cutscene progression, relevant audio, and subtitle lifetime while keeping the current rendered frame unobscured. It must not draw a replacement overlay.

## Current candidate

Current prerelease: **v0.1.0-rc.6**.

rc.6 uses a **hidden vanilla pause** architecture. It does not call a custom pause primitive. KCD2 itself creates and owns the real pause; Clean Pause changes only presentation and input isolation after that vanilla pause is verified.

Retail acceptance of rc.6 is the next gate.

## Retail evidence ledger

### rc.1 / rc.2 — profile routing rejected

Both candidates modified the retail pause actions. Retail testing showed Escape and Xbox Start could be lost entirely.

Conclusions:

- never replace the only vanilla pause route with an unproven custom route;
- exact action-map/profile edits are too risky for the primary implementation;
- `ActionMapManager.InitActionMaps()` remains permanently forbidden because an earlier prototype destroyed controller input globally.

### rc.3 — PAK/Lua/consoleCMD chain proven

The safe F10 diagnostic proved on Xbox Store 1.5.6 that:

- the mod PAK loads;
- `Scripts/Mods/clean_pause.lua` executes;
- `System.AddCCommand` works;
- a profile `consoleCMD` can reach the registered command.

The tested `Game.PauseGame` binding was unavailable. Therefore F10 doing nothing visually in rc.3 was a pause-API failure, not an input-routing failure.

### rc.4 — invalid native ABI, exact root cause

Retail result:

```text
Escape / Start
  -> hook fires
  -> gameplay continues
  -> subsequent gameplay input is swallowed
```

The native log showed the hook declaring pause success immediately before entering its own Clean Pause state:

```text
IGameFramework::PauseGame(true, true, 0) invoked
Running -> Clean Pause (pause input consumed before ActionMapManager)
```

Two implementation errors caused this:

1. `SSystemGlobalEnvironment + 0x98` was interpreted as `IGameFramework*`. Current KCD2 1.5.6 reverse engineering identifies it as `IGame*` (`wh::game::C_Game`). KCD2 `IGame` slot 13 is `GetName()` and returns `"kcd2"`; rc.4 therefore called the wrong object's method through a PauseGame-shaped function pointer.
2. `SetNativePause()` treated "the call returned without an access violation" as proof of success. It did not verify an actual engine pause state before setting `g_cleanPaused=true` and swallowing input.

This explains the observed failure without requiring any speculative input bug.

Permanent conclusion: **never infer pause ownership from a call merely returning successfully.**

### rc.5 — custom Lua pause primitive rejected for production

The safe F10 diagnostic kept Escape/Start vanilla and probed the retail Lua pause route. Retail testing established that the route can freeze world simulation, but it does not reproduce the complete vanilla pause lifecycle required by this mod: audio/UI continue and subtitle lifetime is not retained correctly.

Conclusion: a custom `CryAction` / `Action` / `Game.PauseGame` call is not the production pause mechanism.

## Corrected KCD2 1.5.6 ABI facts

The active architecture relies only on ABI facts that have current reverse-engineering support:

- `SSystemGlobalEnvironment + 0x98` = `IGame*`, not `IGameFramework*`;
- `SSystemGlobalEnvironment + 0x140` = `IFlashUI*`;
- KCD2 `IGame` slot 12 = `GetLongName()`;
- KCD2 `IGame` slot 13 = `GetName()`;
- `IFlashUI::GetUIElementByInstanceStr` = slot 18;
- `IUIElement::SetVisible` = slot 28;
- `IUIElement::IsVisible` = slot 29;
- the raw input hook is `IInput::PostInputEvent` before ActionMapManager.

The project does **not** currently have a sufficiently proven KCD2 callable contract for `IGameFramework` slot 13. Reverse engineering only identifies it as corresponding to KCD1 `PauseGame`; KCD2 callsites differ from the old stock CryEngine interface. It is therefore forbidden as a production primitive.

## Current architecture — rc.6 hidden vanilla pause

### Running -> Clean Pause

On first Escape / Xbox Start:

1. Perform only read-only eligibility checks. If the game is already in `only_ui` or the context cannot be verified, forward the event and do nothing else.
2. Forward the physical Escape/Start event to KCD2 unchanged.
3. After vanilla processing, verify that KCD2 enabled the `only_ui` filter. This is the evidence that the real vanilla pause/menu path acquired ownership.
4. Resolve the retail `Menu@0` Flash element through `IFlashUI`.
5. Hide only that Menu element with `IUIElement::SetVisible(false)`.
6. Verify the resulting state before entering the mod's hidden-pause state.

If any step after forwarding fails, the result must be the ordinary visible vanilla pause menu. That is a successful fail-open outcome, not a reason to swallow gameplay input.

### Hidden vanilla pause -> Running via B

While the hidden vanilla pause is verified:

1. reveal `Menu@0` inside the same input dispatch;
2. forward B to vanilla KCD2 so normal Back/Resume owns the close/unpause operation;
3. re-check `only_ui`;
4. if `only_ui` is gone, return to Running;
5. if vanilla remains paused, re-hide the Menu only if the element can still be verified.

No custom unpause primitive is used.

### Hidden vanilla pause -> visible vanilla menu

On a second Escape / Start:

1. reveal the already-open `Menu@0`;
2. leave KCD2's vanilla pause state intact;
3. consume the second physical pause input so it does not immediately close the menu;
4. relinquish Clean Pause presentation ownership.

This avoids an explicit unpause/re-pause cycle and therefore avoids an intermediate simulation/audio tick.

## Safety invariants

These are release-blocking requirements:

- never call `ActionMapManager.InitActionMaps()`;
- never replace `Player.OnAction`;
- never persistently remap Start/B/Escape;
- never depend on a complete replacement `defaultProfile.xml` for the active implementation;
- never call the rejected rc.4 inferred `IGameFramework::PauseGame` ABI;
- never use `CryAction.PauseGame`, `Action.PauseGame`, or `Game.PauseGame` as the production pause owner;
- never set a Clean Pause/input-swallow state merely because a call did not crash;
- unrelated input may be swallowed only while a **verified vanilla pause** is already active and the menu is successfully hidden;
- any unresolved runtime condition must fail open to vanilla input/pause behavior.

## Plan

### Stage 1 — retail acceptance of rc.6

Test rc.6 unchanged before further implementation work.

Required observations:

1. title/front-end controller and keyboard behavior remain normal;
2. first Escape in gameplay pauses the complete vanilla lifecycle while leaving no visible pause menu;
3. first Xbox Start behaves identically;
4. B resumes through vanilla behavior without leaking a dialogue/cutscene cancel/skip;
5. a second Escape/Start reveals the already-open vanilla pause menu without an intermediate unpause tick;
6. dialogue speech/progression stops;
7. the same subtitle remains visible longer than its normal lifetime;
8. in-engine cutscene progression/audio stop coherently;
9. repeated entry/resume, save loads, Alt-Tab and controller reconnect do not leave a hidden/inert input state.

Always keep `kcd2_clean_pause_native.log` from any failure.

### Stage 2 — classify any rc.6 failure before changing architecture

Do not patch multiple layers at once. Classify the failure into one of these buckets.

#### A. Vanilla pause works, but Menu cannot be hidden

Investigate only UI resolution/timing:

- exact `Menu` instance id/name;
- whether the first input dispatch is too early to resolve `Menu@0`;
- whether another UI element is the visible pause surface;
- whether visibility is changed again later in the same frame.

Keep vanilla pause ownership intact. Prefer a presentation hook/visibility observation over a custom pause primitive.

#### B. Menu hides, but HUD/subtitle also disappears or expires

Determine whether the subtitle/HUD loss comes from:

- the Menu Flash element itself;
- another vanilla pause UI element;
- the vanilla pause lifecycle changing HUD/subtitle visibility;
- subtitle timers continuing despite full simulation pause.

The likely next direction is to suppress only the pause-menu presentation path after vanilla state acquisition, or restore the affected HUD/subtitle element while leaving vanilla pause counters/audio/dialog state untouched.

Do **not** return to rc.5-style simulation-only pause.

#### C. B does not resume correctly

Keep the pause owner vanilla. Diagnose the normal Back action path and event timing. The fix should forward/emit vanilla Back semantics, not call a custom unpause primitive.

#### D. Second Escape/Start closes the pause or causes a simulation tick

Adjust only the reveal/consume ordering. The target remains: reveal an already-open vanilla menu while retaining vanilla pause ownership continuously.

#### E. Runtime verification fails

Fail open. Improve the verification/locator only if the exact retail evidence supports it. Never compensate by swallowing input earlier.

### Stage 3 — hardening after functional acceptance

Only after the core retail scenarios pass:

- verify repeated pause/resume state transitions;
- verify dialogue and cutscene B/Start isolation;
- verify load/death/front-end transitions;
- verify controller reconnect and Alt-Tab;
- strengthen CI against every previously observed regression;
- ensure the release ZIP remains only `version.dll` + `INSTALL.txt` and passes checksum/integrity checks.

### Stage 4 — stable release gate

A stable `v0.1.0` is blocked until all of the following are true on Xbox Store KCD2 1.5.6:

- complete pause lifecycle is confirmed;
- current subtitle retention is confirmed;
- first pause has no visible menu flash considered unacceptable in normal play;
- B resume is reliable;
- second Start/Escape opens vanilla pause reliably;
- no persistent input loss occurs under failure/repetition/transitions;
- installation/uninstallation is documented and does not conflict silently with an existing unrelated `version.dll` proxy.

Until then, releases remain prereleases.

## Decision rule for future implementation

The guiding rule is:

> Reuse vanilla KCD2 pause ownership and remove only the visual obstruction.

A new custom pause primitive is considered only if retail evidence proves the vanilla pause lifecycle itself cannot satisfy subtitle/frame requirements and there is a separately verified engine API that reproduces all required pause subsystems. Current evidence does not support such a primitive.
