# Research notes

This document records retail observations and the KCD2 1.5.6 facts that constrain the implementation. For the active implementation plan, see [STATUS_AND_PLAN.md](STATUS_AND_PLAN.md).

## Retail input/profile facts

The exact Xbox Store 1.5.6 `defaultProfile.xml` uses two pause actions:

```text
ordinary gameplay        open_menu/open_menu
dialogue/cutscene/etc.   open_pause_menu/open_pause_menu
```

with retail Escape/keybind and Xbox `xi_start` bindings.

`rc.1` and `rc.2` proved that modifying/replacing these vanilla routes can remove normal pause entirely. The active native architecture therefore leaves the retail profile untouched.

Permanent rules derived from those tests:

- do not call `ActionMapManager.InitActionMaps()`;
- do not rely on a supplemental runtime Start map as the primary mechanism;
- do not make a complete `defaultProfile.xml` replacement part of the production architecture.

## rc.3 — command chain proven

`v0.1.0-rc.3` restored vanilla Escape/Start and used only a keyboard F10 diagnostic.

Retail evidence proved:

1. the PAK loads;
2. `Scripts/Mods/clean_pause.lua` executes;
3. `System.AddCCommand` registration works;
4. profile `consoleCMD` dispatch reaches the registered command;
5. the tested `Game.PauseGame` binding is unavailable on the Xbox Store 1.5.6 runtime.

Therefore F10 doing nothing visually in rc.3 was not evidence of failed input dispatch.

## rc.4 — invalid native ABI

`v0.1.0-rc.4` intercepted Escape/Start before ActionMapManager and attempted a direct native pause call.

Observed retail behavior:

- Escape/Start reached the hook;
- gameplay continued;
- subsequent controls became unresponsive.

The native log captured the critical sequence:

```text
IGameFramework::PauseGame(true, true, 0) invoked
Running -> Clean Pause (pause input consumed before ActionMapManager)
```

The implementation then repeatedly attempted the vanilla-menu handoff while retaining the false Clean Pause state.

### Root cause 1 — gEnv +0x98 is IGame*

Current KCD2 1.5.6 reverse engineering identifies:

```cpp
Offsets::IGame* pGame; // SSystemGlobalEnvironment + 0x98
```

KCD2's `IGame` vtable identifies:

```text
slot 12 -> GetLongName() -> "Kingdom Come: Deliverance"
slot 13 -> GetName()     -> "kcd2"
```

rc.4 treated `+0x98` as `IGameFramework*` and called slot 13 through a PauseGame-shaped function pointer. Under the Windows x64 calling convention, extra arguments did not necessarily cause an access violation, so `IGame::GetName()` could return normally and the mod falsely declared pause success.

### Root cause 2 — no state confirmation

`SetNativePause()` treated "the call did not raise a structured exception" as success. It did not verify that KCD2 had actually entered a paused state.

The hook then set its own `g_cleanPaused=true` and swallowed gameplay/dialogue input. That exactly matches the retail symptom: the world remained live while controls appeared dead.

### IGameFramework slot 13 remains unproven

The current reverse-engineered KCD2 `IGameFramework` table marks slot 13 as corresponding to KCD1 `PauseGame`, but does not establish a callable KCD2 signature/semantic contract.

A KCD2 `I_UIMenu` callsite uses framework `+0x68` / slot 13 with KCD2-specific arguments and checks adjacent slot 14 with a `uint16_t` id. This is already enough to reject the stock CryEngine signature assumed by rc.4.

The project must not call that slot as a production pause primitive without a separately established KCD2 contract.

## rc.5 — Lua pause diagnostic result

`v0.1.0-rc.5` removed Start/Escape interception and used only a safe F10 diagnostic to probe the retail Lua pause route.

Retail result established an important distinction:

- a Lua pause binding can freeze world simulation;
- it does **not** reproduce the complete vanilla KCD2 pause lifecycle required by Clean Pause;
- audio/UI continue and subtitle lifetime is not retained correctly.

Therefore the custom Lua pause route is rejected for production even though it can stop simulation.

The useful conclusion from rc.5 is not "Lua pause does not work". It is:

> simulation freeze alone is insufficient; Clean Pause needs the full vanilla pause lifecycle.

## Current direction — reuse vanilla pause ownership

The current candidate is `v0.1.0-rc.6`.

It calls no explicit pause primitive. The first physical Escape/Start event is forwarded to KCD2, then the mod verifies vanilla pause ownership through the `only_ui` filter and hides only the visible pause-menu Flash element.

This architecture is intended to inherit vanilla behavior for:

- simulation;
- dialogue/cutscene suspension;
- audio;
- pause counters/state;
- resume/back handling;

while removing only the visual obstruction.

## Verified ABI facts used by rc.6

Current KCD2 1.5.6 reverse-engineering support:

```text
SSystemGlobalEnvironment + 0x98   = IGame*
SSystemGlobalEnvironment + 0x140  = IFlashUI*
IGame slot 12                     = GetLongName()
IGame slot 13                     = GetName()
IFlashUI::GetUIElementByInstanceStr = slot 18
IUIElement::SetVisible              = slot 28
IUIElement::IsVisible               = slot 29
```

The raw input hook remains `IInput::PostInputEvent` before ActionMapManager.

## Why `only_ui` is the ownership check

The candidate does not treat a function call or pointer lookup as pause success. It forwards the real vanilla pause input and then requires the runtime state KCD2 normally establishes for the pause UI: `ActionMapManager.IsFilterEnabled("only_ui")`.

Only after that state is observed may the mod hide the Menu and begin consuming unrelated input.

This is the direct safety correction for rc.4.

## Remaining retail questions for rc.6

The next retail test must determine:

1. whether first Escape/Start reaches full vanilla pause before the Menu is hidden;
2. whether `Menu@0` is the complete visible obstruction on this retail build;
3. whether hiding it can happen without an unacceptable visible flash;
4. whether HUD/subtitle presentation remains visible during the underlying vanilla pause;
5. whether the same subtitle remains indefinitely while paused;
6. whether audio/dialogue/cutscene behavior matches normal vanilla pause;
7. whether B can use vanilla Back to resume while the menu was hidden;
8. whether second Escape/Start can reveal the already-open menu without an intermediate unpause;
9. whether repeated transitions always fail open instead of leaving live gameplay with swallowed input.

Compilation and CI cannot answer these questions. They can only verify Windows build/package integrity, structural ABI guards, ordering invariants, and absence of previously rejected pause primitives.

## External reverse-engineering references

The current KCD2 1.5.6 ABI facts are cross-checked against the public `JerryYOJ/libKCD2` reverse-engineering project, especially:

- `include/crysystem/SSystemGlobalEnvironment.h`;
- `include/Offsets/vtables/IGame.h`;
- `include/Offsets/vtables/IGameFramework.h`;
- `include/guimodule/I_UIMenu.h`;
- `include/guimodule/C_UIMenu.h` / `src/guimodule/C_UIMenu.cpp`.

Treat annotations explicitly marked tentative/unverified there as research hints, not production contracts.
