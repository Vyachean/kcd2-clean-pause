# RC7d retail evidence — Xbox Store KCD2 1.5.6

Source: user retail session on 2026-08-24 using `v0.1.0-rc.7d`.

## User-visible result

The user reported **no visible difference from rc7c**:

- Clean Pause still used the real vanilla pause lifecycle and hid the pause menu correctly;
- world/audio behavior remained as previously established;
- HUD, hints and subtitles were still absent in Clean Pause;
- the accepted vanilla pause depth-of-field blur remained;
- direct Xbox B resume still did not occur.

No additional retail launch is required to diagnose this result.

## Runtime evidence

The rc7d log proves all of the root-level HUD mechanisms were actually active:

```text
hud@0 subtitle-preservation hook active
hud@0 concrete visibility hook active
global HUD visibility hook active
Clean Pause HUD presentation verified: hud@0 visible=true
Running -> Clean Pause candidate: vanilla Menu@0 remains visible but its Render is suppressed
Clean Pause render suppression observed for Menu@0
```

The same session also records the physical controller ids:

```text
key=516 name=xi_start
key=527 name=xi_b
key=541 name=xi_thumbr_down
key=527 name=xi_b
key=526 name=xi_a
```

There is **no** `B resume: replaying vanilla pause ...` line after either `xi_b` press.

## Conclusions

### Root HUD visibility hypothesis rejected

`hud@0::IsVisible() == true` while the user sees no HUD proves that the whole `hud` Flash element's visibility flag is not the presentation state that vanilla pause uses to hide the gameplay HUD.

Persistent suppression of both:

- `IFlashUI::SetHudElementsVisible(false)`; and
- `hud@0::SetVisible(false)`

is therefore insufficient and must not be extended with more whole-element visibility hacks.

Subsequent libKCD2 static analysis identifies `C_UIHudMask` as the deeper layer: it evaluates active UI sources into a 28-bit per-widget visibility set and pushes `name + bool` to 28 child movie clips inside the still-visible `hud` movie. This directly explains the rc7d observation.

### B failure root cause proven

The project's old `KeyId` enum incorrectly assumed the XInput ids were contiguous from 512. That made the compiled values `XiA=522` and `XiB=523`.

Retail evidence proves:

- `XiStart = 516`;
- `XiA = 526`;
- `XiB = 527`.

Therefore physical B reached `PostInputEvent`, but could never match `key == KeyId::XiB`; it fell into the generic Clean Pause input-consumption path before the replay code.

The captured-pause-key replay mechanism itself remains **unverified**, not rejected. rc7e fixes the enum with explicit retail-proven values and will be the first valid test of that resume route.

## Next candidate

`v0.1.0-rc.7e` removes the rejected root HUD visibility hooks. Before vanilla pause changes UI-source state it snapshots the visible state of all 28 `hud` child movie clips through verified `IUIElement::GetMovieClip` / `IFlashVariableObject::GetDisplayInfo`, then restores the exact snapshot during the pause transition through `IFlashVariableObject::SetVisible`.

This remains storefront-independent: it uses verified interface vtable slots and no fixed WHGame RVAs.
