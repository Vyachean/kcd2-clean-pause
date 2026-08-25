#pragma once

namespace clean_pause::hud_mask {

using MutationObserver = void(*)();

// Hooks the concrete KCD2 1.5.6 C_UIHudMask mutation entry points discovered from
// hud@0's listener list by MSVC RTTI. The observer runs immediately after vanilla
// updates its internal HUD-mask state, before control returns to the caller/render.
bool EnsureHooks(void* hudElement, MutationObserver observer);

} // namespace clean_pause::hud_mask
