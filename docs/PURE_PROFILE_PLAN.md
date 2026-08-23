# Pure-profile implementation plan

Primary target: Kingdom Come: Deliverance II 1.5.6 on PC Xbox Store / Xbox app / Game Pass.

## Product requirement

Clean Pause must stop gameplay/dialogue/cutscene progression while leaving the current rendered frame and current subtitles unobscured. It must not show a custom overlay or the vanilla pause menu on the first pause action.

Preferred controller UX:

```text
Running
  Menu/Start -> Clean Pause

Clean Pause
  B          -> Resume
  Menu/Start -> vanilla pause menu
```

Keyboard parity should use Escape with the same state transitions when practical.

## Constraints

The primary implementation must remain a normal KCD2 `.pak` mod:

- no `version.dll`, ASI, KCSE, DetourModKit, or external process;
- no runtime `InitActionMaps()`;
- no runtime supplemental Start action through `LoadFromXML()` (proved ineffective on Xbox Store 1.5.6 in PR #2);
- no `Menu.gfx` replacement unless every profile/action-level option is exhausted;
- use the retail `Game.PauseGame(true/false)` pause primitive rather than `t_scale` unless retail behavior disproves it.

## Evidence supporting this path

Current KCD2 mods bind controller actions through `Libs/Config/defaultProfile.xml`. Magus Quicksave publicly documents an Xbox/PS controller action bound to `xi_start`, proving that a normal packaged profile can receive Start when it participates in the game's normal profile-loading path.

KCD2 modding documentation also treats `defaultProfile.xml` and `keybindSuperactions.xml` as the normal keybinding data files. These files are whole-file overrides unless a separate merge/extender system is used, so compatibility with other keybind mods must be documented.

## Implementation stages

### Stage 1 — establish the exact 1.5.6 vanilla pause binding

Obtain a trustworthy 1.5.6 `Libs/Config/defaultProfile.xml` or an equivalent current extracted profile and determine:

- action-map name that owns the pause action;
- exact action name (`ui_start_pause` is expected but must be verified from the file used for implementation);
- Xbox token (`xi_start`);
- keyboard token (Escape);
- any superaction/filter dependencies relevant to pause.

Do not author a replacement profile from memory.

### Stage 2 — minimal profile patch

Create a complete 1.5.6-compatible `defaultProfile.xml` derived from the verified base profile and change only the minimum necessary pause entries.

The profile should route Start/Escape to a console-command action owned by Clean Pause and prevent the original pause action from firing on that same press.

All unrelated vanilla bindings must be byte-for-byte or semantically identical to the verified base where feasible.

### Stage 3 — Lua state machine

Implement explicit states:

```text
RUNNING
CLEAN_PAUSED
```

Transitions:

- RUNNING + pause action -> `Game.PauseGame(true)`, state CLEAN_PAUSED;
- CLEAN_PAUSED + B -> `Game.PauseGame(false)`, state RUNNING;
- CLEAN_PAUSED + pause action -> resume Clean Pause and invoke the untouched vanilla pause-menu path.

The vanilla-menu invocation must be verified from KCD2's existing Lua/UI APIs or existing game scripts. Do not simulate a raw controller action from Lua unless proven to reach the same UI path.

### Stage 4 — safe menu handoff

Find and prove the least invasive way to open the real pause menu from Lua. Candidate order:

1. documented/retail UI event-system call for the ingame menu;
2. an existing Game/UI Lua binding used by retail scripts;
3. a narrowly replaced vanilla pause action that can be temporarily enabled/disabled through profile-defined filters.

Avoid replacing `Menu.gfx`.

### Stage 5 — build validation

CI must verify:

- Lua 5.1 syntax;
- XML parseability;
- no executable `InitActionMaps()`;
- expected profile action names and controller tokens;
- PAK contains only expected files;
- no native DLL/ASI files in the pure-profile artifact.

### Stage 6 — retail acceptance on Xbox Store 1.5.6

Test in this order:

1. controller works normally in the title screen;
2. load a save and verify normal movement/actions;
3. Start produces Clean Pause with no vanilla-menu frame;
4. current subtitle remains visible;
5. dialogue/cutscene/audio progression behavior is recorded;
6. B resumes;
7. Start from Clean Pause opens the normal KCD2 pause menu;
8. closing vanilla pause returns to normal gameplay;
9. repeat during dialogue/cutscene and ordinary gameplay;
10. verify front-end and other UI screens retain vanilla Start/B behavior.

## Compatibility policy

A pure `.pak` implementation that replaces `defaultProfile.xml` can conflict with other mods that replace the same file. This is acceptable for the initial implementation if:

- the conflict is documented clearly;
- the exact Clean Pause additions/replacements are documented for manual merging;
- no unrelated keybind changes are introduced.

PTFextender or another merge dependency may be offered later as an optional compatibility path, not as a requirement for the core mod.

## Fallback policy

The native prototype in PR #3 remains a fallback only. It should not be merged or released unless the pure-profile approach is demonstrated to be technically incapable of satisfying the product requirement on Xbox Store 1.5.6.
