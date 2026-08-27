# RC7c retail evidence — Xbox Store KCD2 1.5.6

Source: user retail session on 2026-08-24.

Observed behavior:

- Clean Pause still pauses the game and hides the pause menu.
- User reported no visible difference from rc7b.
- HUD, subtitles, and hints were still not visible during Clean Pause.
- Strong vanilla pause depth-of-field blur remained; accepted as out of scope.

Relevant runtime evidence:

```text
rc7c HUD-preserving render-suppression candidate active
Menu@0 render hook active
hud@0 subtitle-preservation hook active
Running -> Clean Pause candidate: vanilla Menu@0 remains visible but its Render is suppressed
Clean Pause render suppression observed for Menu@0
Clean Pause subtitle freeze: suppressed hud.ClearSubtitles
```

Interpretation:

1. `hud@0` resolves correctly on this retail build.
2. The named HUD `CallFunction` hook is active and can intercept `ClearSubtitles`.
3. `IFlashUI::SetHudElementsVisible(true)` is not sufficient to make the concrete HUD presentation visible during vanilla pause.
4. The next candidate should control actual `hud@0` visibility while Clean Pause is active and preserve the narrow subtitle-clear suppression.
5. This session does not verify direct B resume because the log contains Escape interactions only; no physical B event was recorded while Clean Pause was active.
