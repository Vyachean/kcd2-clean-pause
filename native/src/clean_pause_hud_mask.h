#pragma once

#include <cstddef>

namespace clean_pause::hud_mask {

using MutationObserver = void(*)();
inline constexpr std::size_t kHudElementCount = 28;

// Hooks the concrete KCD2 1.5.6 C_UIHudMask mutation entry points discovered from
// hud@0's listener list by MSVC RTTI. The observer runs immediately after a verified
// vanilla HUD-mask mutation, before control returns to the caller/render.
bool EnsureHooks(void* hudElement, MutationObserver observer);

// Reads KCD2's current source-derived HUD visibility from I_UIHudMask rather than
// from the Flash clips. The caller supplies storage for exactly 28 element values.
// The hook layer retains only validated C_UIHudMask/source-monitor identities for
// detour scoping; callers receive no borrowed object and no movieclip pointer is retained.
bool ReadCurrentVisibility(void* hudElement, bool* visible, std::size_t count);

} // namespace clean_pause::hud_mask
