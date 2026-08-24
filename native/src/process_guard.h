#pragma once

namespace clean_pause {

// Returns true only for the first Clean Pause native module loaded in this
// game process. The winning guard is intentionally held until process exit:
// hot-unloading is unsupported because native hooks remain process state.
bool AcquireProcessGuard();

} // namespace clean_pause
