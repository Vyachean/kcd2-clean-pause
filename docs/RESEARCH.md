# Historical research notes

> **Status: historical evidence, not an implementation plan.** For current behavior and architecture use [README.md](../README.md), [STATUS_AND_PLAN.md](STATUS_AND_PLAN.md), and [DESIGN.md](DESIGN.md).

This document summarizes the retail observations that led to the current KCD2 1.5.6 implementation. Older candidate names below are historical and must not be interpreted as the current `v0.2.0-rc.N` release sequence.

## Retail input/profile facts

The Xbox Store 1.5.6 `defaultProfile.xml` exposes separate Start routes for ordinary gameplay and dialogue/cutscene contexts, both ultimately bound to `xi_start`.

Early `v0.1.0-rc.1` / `v0.1.0-rc.2` experiments showed that replacing or modifying those routes can remove normal pause entirely. The production architecture therefore leaves the retail action profile untouched.

Permanent conclusions:

- do not use action-map/profile replacement as the primary pause path;
- do not call `ActionMapManager.InitActionMaps()` as part of Clean Pause;
- do not rely on a supplemental runtime Start action for ownership.

## v0.1.0-rc.3 — command chain diagnostic

The historical F10 diagnostic proved that the PAK/Lua command chain could load and dispatch correctly. It also showed that the tested `Game.PauseGame` route was not a reliable production pause primitive on the target build.

The useful result was diagnostic reachability, not a viable pause implementation.

## v0.1.0-rc.4 — invalid native pause assumption

A native prototype intercepted Escape/Start and attempted an inferred pause vfunc. Retail behavior showed gameplay remaining live while controls became unresponsive.

The root cause was an invalid ABI assumption:

```text
SSystemGlobalEnvironment + 0x98 -> IGame*
```

The prototype treated that object as `IGameFramework*` and considered a non-crashing call to be successful without independently proving game pause state.

Permanent conclusions:

- never infer pause success from a call merely returning;
- never use an unproven `IGameFramework::PauseGame` signature as production ownership;
- fail open rather than entering a mod-owned pseudo-pause state.

## v0.1.0-rc.5 — simulation freeze is insufficient

The next diagnostic established that a Lua-accessible pause/freeze route could stop world simulation but did **not** reproduce the complete vanilla KCD2 pause lifecycle. Audio/UI/subtitle behavior differed from real pause.

This separated two concepts that had previously been conflated:

> freezing simulation is not the same as owning the vanilla pause lifecycle.

That result permanently rejected custom Lua/native pause ownership for this mod.

## Reusing vanilla pause ownership

Later candidates changed direction: the real Escape/Start input was forwarded to KCD2 and the mod attempted to remove only the visible pause presentation.

One intermediate design used the `only_ui` action filter as ownership evidence. Retail work later showed that this was not a sufficient lifecycle signal. The accepted signal became:

```text
Menu@0::IsVisible()
```

The accepted presentation architecture became:

- leave `Menu@0` logically visible;
- suppress only `Menu@0::Render()` while Clean Pause is active;
- let KCD2 remain the sole pause owner.

This is the foundation still used by the current production implementation.

## HUD/subtitle evidence

Retail testing showed that root `hud@0` visibility is not enough: KCD2 changes individual HUD child clips during pause.

Experiments then established the current safety rules:

- the relevant main-HUD presentation is represented by 28 named child movie clips;
- snapshots store visibility booleans, not raw movieclip pointers;
- `IUIElement::GetMovieClip()` results are borrowed/call-local;
- those results must never be retained across frames or destructively `Release()`d;
- bounded presentation maintenance belongs on validated `hud@0::Update(float)`, not `Menu@0::Render()`.

Historical `rc7e`, `rc7f`, and `rc7g` evidence files record the pointer-lifetime/crash sequence that led to these rules.

## Current extensions derived later

After the initial `v0.1.0` stable architecture was proven, the `0.2.0` feature line added two bounded presentation features without changing pause ownership:

- exact DoF capture/suppression/restoration for a sharp Clean Pause frame;
- preservation of live NPC overhead subtitle objects through the `C_UIHudBubbles` lifecycle.

These are documented in [DESIGN.md](DESIGN.md), not in the historical candidate plans.

## Reverse-engineering boundary

Public KCD2 reverse-engineering sources such as `JerryYOJ/libKCD2` were used as supporting evidence for interface layout and class relationships. Tentative annotations remain hints only; production contracts require either direct retail evidence or bounded runtime validation.

For the authoritative list of permanently rejected paths and current accepted rules, see [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md).
