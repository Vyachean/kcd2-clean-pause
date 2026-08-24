# RC6 C_UIMenu state diagnostic

This is a temporary **read-only** diagnostic for Xbox Store / Xbox app KCD2 1.5.6.

It exists because the first rc.6 diagnostic proved:

- `Menu@0` resolves correctly;
- its `IsVisible()` value tracks the visible vanilla pause menu;
- `ActionMapManager.IsFilterEnabled("only_ui")` remains false even while the vanilla pause menu is visibly open for seconds.

Therefore `only_ui` cannot be the production pause-ownership signal on this retail build.

## What this probe tests

Current KCD2 1.5.6 reverse engineering identifies the real menu controller as `wh::guimodule::C_UIMenu`:

- `S_GameContext + 0xE8` -> `C_GUIModule*`;
- `C_GUIModule + 0x40` -> `std::vector<std::shared_ptr<C_UIBase>>`;
- `C_UIFlashBase + 0x48` -> bound `IUIElement*`;
- `C_UIMenu` contains an `I_UIMenu` interface at `+0x58`;
- `C_UIMenu + 0xA0` is the menu mode/state byte;
- `I_UIMenu::GetState` is interface slot 9.

Expected state values from the reverse-engineered 1.5.6 controller:

```text
0 = closed
1 = root main menu
2 = in-game pause menu
3 = restricted pause menu
4 = death/main variant
5 = photomode
```

The probe does not trust only one field. A controller candidate is accepted only when:

1. the containing object is in the live `GUIModule` UI-elements vector;
2. its bound Flash element pointer equals the independently resolved `Menu@0`;
3. the `I_UIMenu` subobject has executable required vtable slots;
4. slot 9 returns a value in 0..5;
5. that value exactly matches the independently read `C_UIMenu + 0xA0` state byte.

## Safety

This DLL:

- installs no input hook;
- consumes no input;
- does not call `PauseGame`;
- does not call `SetVisible`;
- does not modify action maps or filters;
- polls state read-only every 100 ms;
- leaves ordinary KCD2 UI and controls untouched.

## Test

1. Close KCD2.
2. Replace the previous diagnostic `version.dll` with the one from the `rc6-menu-mode-diagnostic` Actions artifact.
3. Delete or rename the old `kcd2_clean_pause_native.log`.
4. Start KCD2 and load a save.
5. Wait a few seconds in normal exploration.
6. Press Xbox Start and leave the ordinary vanilla pause menu open for about one second.
7. Close it with B.
8. Repeat with Escape.
9. If practical, repeat once during dialogue so KCD2 can exercise its restricted pause route.
10. Send the new `kcd2_clean_pause_native.log`.

## Expected decisive result

For normal gameplay the desired trace is approximately:

```text
flash_visible=false menu_state=0
-> Start/Escape
flash_visible=true  menu_state=2
-> B
flash_visible=false menu_state=0
```

Dialogue/cutscene pause may report state `3` instead of `2`.

If this relationship is confirmed, the next functional candidate can safely use `C_UIMenu` state as vanilla pause ownership and use `Menu@0::SetVisible(false)` only as presentation. That preserves the rc.6 architectural rule: KCD2 owns pause; the mod hides only the obstruction.
