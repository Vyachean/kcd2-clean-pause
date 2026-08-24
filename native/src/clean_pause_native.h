#pragma once

#include <windows.h>

namespace clean_pause {

// Starts the deferred runtime locator/hook installation. Safe to call from the
// proxy DLL process-attach path; implementation performs no heavy work under
// the loader lock.
bool Start(HMODULE selfModule);

// Best-effort shutdown used on process detach. The game process normally tears
// the module down as a whole, so this is intentionally conservative.
void Stop();

} // namespace clean_pause
