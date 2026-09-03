#pragma once

#include <windows.h>

namespace clean_pause {

// Starts the deferred runtime locator/hook installation. Safe to call from the
// proxy DLL process-attach path; implementation performs no heavy work under
// the loader lock.
bool Start(HMODULE selfModule);

// Marks the runtime as stopping during normal process teardown. Clean Pause hooks
// are process-lifetime state: Stop() does not remove MinHook detours and must not
// be interpreted as support for loader-initiated hot unload/reload.
void Stop();

} // namespace clean_pause
