#include "clean_pause_native.h"
#include "process_guard.h"

#include <windows.h>

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID)
{
    switch (reason) {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(instance);
        if (clean_pause::AcquireProcessGuard())
            clean_pause::Start(instance);
        break;
    case DLL_PROCESS_DETACH:
        clean_pause::Stop();
        break;
    default:
        break;
    }
    return TRUE;
}
