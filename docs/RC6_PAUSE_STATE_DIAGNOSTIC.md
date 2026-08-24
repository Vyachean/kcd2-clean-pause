# rc.6 vanilla pause-state diagnostic

This is a temporary **read-only retail diagnostic** for Xbox Store / Xbox app KCD2 1.5.6.

It exists because retail rc.6 forwarded Escape/Start successfully but never observed the expected `only_ui` state, so it correctly failed open to the ordinary visible KCD2 pause menu.

## What this build does

The diagnostic hooks the same `IInput::PostInputEvent` location as rc.6, but it does **not** implement Clean Pause.

It only records, before/after vanilla pause input and on later input events:

- whether the Lua context probe succeeded;
- `player ~= nil`;
- `ActionMapManager.IsFilterEnabled("only_ui")`;
- whether `Menu@0` can be resolved through `IFlashUI`;
- whether `Menu@0` reports itself visible through `IUIElement::IsVisible`.

The diagnostic never calls `IUIElement::SetVisible`, never calls a pause/unpause primitive, never changes action maps or filters, and never consumes input. Every non-null input event is forwarded to KCD2 exactly once.

## Expected game behavior

**Everything should look and behave exactly like unmodded KCD2.**

Escape / Xbox Start should open the ordinary visible vanilla pause menu. B and normal menu navigation should behave normally.

If this diagnostic changes visible game behavior, stop the test and keep the log.

## Install

1. Close KCD2.
2. Make sure the old profile mod is absent/disabled:

   `%USERPROFILE%\Documents\kingdomcome_mods\clean_pause`

3. Replace the previous Clean Pause `version.dll` beside `KingdomCome.exe` / `WHGame.dll` with the `version.dll` from the diagnostic artifact.
4. Do not overwrite an unrelated mod's `version.dll`.
5. Start KCD2 normally.

The diagnostic appends to:

`kcd2_clean_pause_native.log`

beside `version.dll`.

For a clean result, deleting or renaming the old log before starting the game is recommended.

## Test A — Xbox Start

1. Load a save and stand in normal exploration.
2. Press Xbox **Start/Menu** once.
3. Confirm that the normal visible KCD2 pause menu opens.
4. Leave it open for about one second.
5. Press D-pad Down once (or another harmless menu-navigation direction) so the probe gets a later input event while the menu is definitely open.
6. Close the menu normally with B.

## Test B — Escape

Repeat the same sequence with keyboard **Escape**.

## Optional dialogue sample

If convenient, repeat one pause during dialogue. Do not evaluate Clean Pause behavior in this build; only confirm ordinary vanilla pause behavior.

## Log lines of interest

Successful bootstrap:

```text
rc6 pause-state diagnostic hook active; vanilla input untouched
```

Each sample uses this form:

```text
pause-state snapshot phase=... context_ok=... has_player=... only_ui=... menu_lookup_ok=... menu_resolved=... menu_visibility_ok=... menu_visible=...
```

The important comparison is between:

- `pause-press-before-forward`;
- `pause-press-after-forward`;
- `pause-release-after-forward`;
- `followup-after-forward` while the visible vanilla menu is known to be open.

## Decision from the result

- If `only_ui` becomes `true` only on a later sample, rc.6 has a timing/observation-point problem.
- If `only_ui` remains `false` while `Menu@0` resolves and reports `menu_visible=true`, `only_ui` is not a valid retail ownership invariant for this pause path; the next implementation must use another verified state signal.
- If `Menu@0` does not resolve or does not report visible while the pause menu is visibly on screen, the UI locator/visibility assumption must be corrected before any hiding logic is attempted.

Return the complete new `kcd2_clean_pause_native.log` after the two main tests.
