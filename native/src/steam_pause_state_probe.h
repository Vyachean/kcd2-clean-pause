#pragma once

#include <windows.h>

namespace clean_pause {

// Acceptance-only Steam diagnostic; never part of the standalone publication path.
bool StartSteamPauseStateProbe(HMODULE selfModule);
void StopSteamPauseStateProbe();

} // namespace clean_pause
