#pragma once

#include <windows.h>

namespace clean_pause {

bool StartSteamPauseStateProbe(HMODULE selfModule);
void StopSteamPauseStateProbe();

} // namespace clean_pause
