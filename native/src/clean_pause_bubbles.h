#pragma once

namespace clean_pause::bubbles {

// Best-effort installation of the narrow NPC speech-bubble preservation hooks.
// Failure must never disable the already-proven Clean Pause path.
bool EnsureHooks(void* hudElement, void* flashUI);

} // namespace clean_pause::bubbles
