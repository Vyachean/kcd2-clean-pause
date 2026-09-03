#pragma once

namespace clean_pause::bubbles {

// The Menu@0 visibility observer patches the shared CFlashUIElement::SetVisible
// method. Reuse that one patch for a narrowly-scoped hud@0 root-visibility filter
// instead of trying to install a second MinHook detour on the same function body.
// Return true to suppress the requested hud@0 SetVisible call.
using HudRootVisibilityFilterFn = bool(*)(bool visible);
void SetHudRootVisibilityFilter(HudRootVisibilityFilterFn filter);

// Best-effort installation of the narrow NPC speech-bubble preservation hooks.
// Failure must never disable the already-proven Clean Pause path. The shared
// Menu/hud SetVisible observer is installed independently so root-HUD preservation
// can remain available even when bubble RTTI discovery is unavailable.
bool EnsureHooks(void* hudElement, void* flashUI);

} // namespace clean_pause::bubbles
