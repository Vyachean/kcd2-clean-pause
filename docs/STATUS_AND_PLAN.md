# Current status and plan

Canonical project status for KCD2 Clean Pause.

## Target UX

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  B              -> Running
  Escape / Start -> visible vanilla pause menu
```

Target: KCD2 1.5.6 Windows retail, primarily PC Xbox Store / Xbox app, Xbox controller first.

Clean Pause must preserve vanilla KCD2 pause ownership so gameplay, dialogue/cutscene progression, relevant audio and subtitle lifetime stop while the current game frame remains unobscured. Vanilla depth-of-field blur is accepted.

## Accepted pause foundation

Retail-proven:

- forward the real Escape/Start event to KCD2;
- use `Menu@0::IsVisible()` as the independent vanilla-pause lifecycle signal;
- never change `Menu@0` visibility;
- suppress only `Menu@0::Render()` while Clean Pause owns presentation;
- second Start/Escape reveals the already-open vanilla menu without an unpause/re-pause tick;
- world simulation and audio pause correctly;
- unresolved state fails open.

## Retail-proven HUD layer

rc7c/rc7d proved root HUD visibility is insufficient.

KCD2's `C_UIHudMask` controls 28 named child movie clips inside `hud@0`. rc7e preserved those children and produced the first confirmed positive result: **the subtitle at the bottom remained visible during Clean Pause**.

Therefore the 28-child layer is accepted. Do not return to root-HUD visibility experiments.

## rc7e result

Sequence:

1. Start -> Clean Pause;
2. subtitle visible;
3. second Start -> visible vanilla menu;
4. B -> crash.

The rc7e implementation retained raw movieclip pointers across frames, which was rejected as a stale/cross-thread lifetime risk. However, later evidence shows those pointers also must not simply be `Release()`d by the caller.

## rc7f result — immediate first-pause crash

The game launched normally but crashed immediately when the first pause was attempted.

Last native markers:

```text
rc7f ... candidate active
Menu@0 render hook active
hud@0 subtitle-preservation hook active
hud@0 main-thread Update hook active
HUD visibility snapshot captured for all 28 clips (gameplay-pre-pause)
Clean Pause subtitle freeze: suppressed hud.ClearSubtitles
```

No vanilla-pause snapshot or Clean Pause entry was reached.

This localizes the crash to the transition immediately after the complete gameplay snapshot.

See `docs/RETAIL_EVIDENCE_RC7F.md`.

## Corrected ownership conclusion

RC7f introduced immediate `Release()` calls for every `IUIElement::GetMovieClip()` result.

That ownership assumption is unsupported and conflicts with CryEngine's documented IUIElement usage:

- `IUIElement::GetMovieClip()` is shown as returning a pointer used directly, with no caller `Release()` requirement;
- the documentation separately requires `Release()` for variable objects created through the raw `IFlashPlayer` interface;
- libKCD2 confirms `IFlashVariableObject::Release()` is destructive (`delete this`).

The rc7f log is consistent with deleting movieclip wrappers owned/cached by the UI element and then crashing when the pause transition touches them.

## Active candidate — v0.1.0-rc.7g

RC7g uses the following ownership rule for `IUIElement::GetMovieClip()`:

- pointer is borrowed/cached;
- use only during the current helper call;
- never store in global/snapshot state;
- never call `Release()`;
- snapshot stores only visibility booleans.

Thus rc7g avoids both rejected extremes:

- rc7e: raw movieclip pointers retained across frames;
- rc7f: borrowed movieclip pointers destructively released.

## Dual bool-only HUD snapshots

RC7g retains the symmetric rc7f state model:

1. capture gameplay child visibility before forwarding physical pause;
2. after real vanilla pause opens, capture vanilla-pause child visibility;
3. restore gameplay snapshot for Clean Pause;
4. on second Start/Escape restore vanilla-pause snapshot before revealing Menu;
5. on direct B restore vanilla-pause snapshot before replaying the vanilla pause toggle.

No child is blindly forced visible.

## HUD maintenance and diagnostics

`Menu@0::Render()` remains presentation-only.

Verified `IUIElement::Update(float)` slot 23 on resolved `hud@0` performs bounded late snapshot maintenance only while Clean Pause is active and only on the validated main thread.

RC7g adds one-shot diagnostic markers around the first Update trampoline:

```text
hud@0 Update hook first entry ...
hud@0 Update original returned successfully
```

If another crash occurs, one log distinguishes Update-hook/trampoline failure from snapshot logic without a separate diagnostic run.

## Input facts

Retail-proven Xbox ids:

- Start = 516;
- A = 526;
- B = 527.

Physical B is consumed while Clean Pause owns input; it must not leak into gameplay/dialog/cutscene actions.

Direct B replay remains to be fully retail-proven.

## Permanent rejected paths

Do not reintroduce without new direct evidence:

- profile/action-map routing as primary pause interception;
- action-map reload/remapping or `Player.OnAction` replacement;
- inferred/custom/Lua `PauseGame` production ownership;
- `only_ui` as vanilla pause evidence;
- `Menu@0::SetVisible(false)`;
- fixed storefront-dependent libKCD2 WHGame RVAs;
- aggressive writable-section `S_GameContext` scanning;
- root/global HUD visibility as complete child presentation;
- contiguous inferred XInput ids;
- raw `GetMovieClip()` pointers retained across frames;
- `Release()` on `IUIElement::GetMovieClip()` results;
- HUD child mutation from `Menu@0::Render()`.

## Active ABI facts

- `IFlashUI::GetUIElementByInstanceStr` = 18
- `IUIElement::Update(float)` = 23
- `IUIElement::Render()` = 24
- `IUIElement::SetVisible` = 28
- `IUIElement::IsVisible` = 29
- named `IUIElement::CallFunction` = 69
- `IUIElement::GetMovieClip(name)` = 71
- `IFlashVariableObject::GetDisplayInfo` = 26
- `IFlashVariableObject::SetVisible` = 33
- Xbox `XiStart=516`, `XiA=526`, `XiB=527`

`IFlashVariableObject::Release` exists at slot 0 but is **not an ownership operation permitted on `IUIElement::GetMovieClip()` results in the active candidate**.

## RC7g single-session gate

Only after generated-source safety checks, MSVC x64 build, proxy/dependency checks and exact prerelease publication are green, use one retail session:

1. first Start must not crash;
2. subtitle/HUD should remain visible in Clean Pause;
3. second Start -> visible vanilla menu -> B must be stable;
4. direct B from Clean Pause should resume without visible menu flash/skip/cancel;
5. repeat both transitions several times;
6. if a spoken subtitle is naturally available, hold pause beyond its normal lifetime.

If anything crashes/fails, do not repeat the launch; one fresh native log is enough.

## Stable release gate

Stable `v0.1.0` remains blocked until retail confirms:

- first pause stable;
- subtitle/HUD retention;
- dialogue/cutscene/audio pause coherence;
- direct B resume;
- visible vanilla menu transition and B stability;
- repeated use stability;
- fail-open behavior;
- installation/uninstallation/proxy conflict documentation.

## Decision rule

> Reuse vanilla KCD2 pause ownership, preserve exact HUD child visibility as bool state, and treat `IUIElement::GetMovieClip()` pointers as call-local borrowed handles only.
