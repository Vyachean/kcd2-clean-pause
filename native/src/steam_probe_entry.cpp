#include "steam_runtime_probe.h"

#include <windows.h>

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID)
{
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        clean_pause::steam_probe::Start(instance);
    }
    return TRUE;
}
