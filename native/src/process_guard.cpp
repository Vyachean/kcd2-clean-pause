#include "process_guard.h"

#include <windows.h>
#include <strsafe.h>

namespace clean_pause {
namespace {

HANDLE g_processGuard{};

} // namespace

bool AcquireProcessGuard()
{
    if (g_processGuard)
        return true;

    wchar_t name[96]{};
    if (FAILED(StringCchPrintfW(
            name,
            sizeof(name) / sizeof(name[0]),
            L"Local\\KCD2CleanPauseRuntime-%lu",
            static_cast<unsigned long>(GetCurrentProcessId()))))
        return false;

    HANDLE guard = CreateMutexW(nullptr, FALSE, name);
    if (!guard)
        return false;

    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        CloseHandle(guard);
        return false;
    }

    // Keep this handle for the lifetime of the process. Clean Pause does not
    // support hot-unloading because its native hooks are process state; keeping
    // the guard prevents another edition from starting after an unsafe unload.
    g_processGuard = guard;
    return true;
}

} // namespace clean_pause
