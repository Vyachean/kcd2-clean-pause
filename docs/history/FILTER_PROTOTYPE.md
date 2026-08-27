# Deterministic action-filter prototype

> **Status: rejected historical prototype.** This document records an early action-map/filter design. Retail testing later rejected profile/action routing and custom `PauseGame` ownership for production. Do not use this as implementation guidance. See [DESIGN.md](DESIGN.md) and [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md).

## Historical idea

The prototype attempted to prevent KCD2's vanilla `ui_start_pause` action from dispatching while routing the same physical Xbox Menu/Start input to a separate `clean_pause_start` action.

Conceptually:

```text
physical xi_start
  |
  +-- ui_start_pause       -- filtered before dispatch
  |
  +-- clean_pause_start    -- allowed -> custom pause owner
```

The design also proposed a custom B action and an `actionPass` filter for input isolation while a mod-owned pause was active.

## Why it was attractive

CryEngine evaluates action filters before an action is added to the event priority list, so the approach appeared capable of avoiding a timing race between vanilla pause and custom pause handling.

It also avoided persistent controller remapping and attempted to preserve ordinary input outside Clean Pause.

## Why it is rejected

Retail development established several stronger constraints:

- supplemental/custom Start routing was not a reliable basis for the target Xbox Store build;
- action-map/profile replacement introduced avoidable compatibility and input-safety risk;
- custom `Game.PauseGame`/Lua/native pause ownership did not reproduce the complete KCD2 pause lifecycle;
- simulation freeze alone was insufficient for audio, dialogue/cutscene, UI, and subtitle semantics;
- KCD2's own pause lifecycle can be reused directly by forwarding the real Escape/Start input.

The accepted production design therefore does **not** load this custom map/filter configuration and does not use the proposed `clean_pause_start` / `clean_pause_resume` ownership model.

## Historical XML sketch

The prototype investigated a structure similar to:

```xml
<profile version="22">
  <actionmap name="clean_pause_controls" version="22">
    <action name="clean_pause_start" consoleCmd="1" onPress="1" xboxpad="xi_start" />
    <action name="clean_pause_resume" consoleCmd="1" onPress="1" xboxpad="xi_b" />
  </actionmap>

  <actionfilter name="clean_pause_block_vanilla_pause" type="actionFail">
    <filter name="ui_start_pause" />
  </actionfilter>

  <actionfilter name="clean_pause_only" type="actionPass">
    <filter name="clean_pause_start" />
    <filter name="clean_pause_resume" />
  </actionfilter>
</profile>
```

This XML is retained only as historical evidence. It is not packaged or loaded by the current mod.

## Evidence value retained

The prototype remains useful for documenting why the project deliberately avoids:

- `InitActionMaps`;
- custom runtime Start/B action ownership;
- action filters as the primary pause interception mechanism;
- `Game.PauseGame(true/false)` as the Clean Pause lifecycle owner.

For the current architecture, KCD2 owns pause, `Menu@0::IsVisible()` is the lifecycle signal, and Clean Pause suppresses only the presentation that obstructs the retained frame.
