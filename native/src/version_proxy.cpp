#include "clean_pause_native.h"

#include <windows.h>
#include <winver.h>

#include <string>

namespace {

INIT_ONCE g_versionInit = INIT_ONCE_STATIC_INIT;
HMODULE g_realVersion{};

BOOL CALLBACK LoadRealVersion(PINIT_ONCE, PVOID, PVOID*)
{
    wchar_t systemDir[MAX_PATH]{};
    const UINT length = GetSystemDirectoryW(systemDir, MAX_PATH);
    if (length == 0 || length >= MAX_PATH)
        return FALSE;

    std::wstring path(systemDir, length);
    path += L"\\version.dll";
    g_realVersion = LoadLibraryW(path.c_str());
    return g_realVersion != nullptr;
}

HMODULE RealVersion()
{
    if (!InitOnceExecuteOnce(&g_versionInit, LoadRealVersion, nullptr, nullptr))
        return nullptr;
    return g_realVersion;
}

template <typename Fn>
Fn Resolve(const char* name)
{
    HMODULE module = RealVersion();
    if (!module)
        return nullptr;
    return reinterpret_cast<Fn>(GetProcAddress(module, name));
}

template <typename T>
T Missing(T value)
{
    SetLastError(ERROR_PROC_NOT_FOUND);
    return value;
}

} // namespace

extern "C" __declspec(dllexport) BOOL WINAPI GetFileVersionInfoA(
    LPCSTR filename, DWORD handle, DWORD length, LPVOID data)
{
    using Fn = BOOL(WINAPI*)(LPCSTR, DWORD, DWORD, LPVOID);
    const auto fn = Resolve<Fn>("GetFileVersionInfoA");
    return fn ? fn(filename, handle, length, data) : Missing(FALSE);
}

extern "C" __declspec(dllexport) BOOL WINAPI GetFileVersionInfoW(
    LPCWSTR filename, DWORD handle, DWORD length, LPVOID data)
{
    using Fn = BOOL(WINAPI*)(LPCWSTR, DWORD, DWORD, LPVOID);
    const auto fn = Resolve<Fn>("GetFileVersionInfoW");
    return fn ? fn(filename, handle, length, data) : Missing(FALSE);
}

extern "C" __declspec(dllexport) BOOL WINAPI GetFileVersionInfoExA(
    DWORD flags, LPCSTR filename, DWORD handle, DWORD length, LPVOID data)
{
    using Fn = BOOL(WINAPI*)(DWORD, LPCSTR, DWORD, DWORD, LPVOID);
    const auto fn = Resolve<Fn>("GetFileVersionInfoExA");
    return fn ? fn(flags, filename, handle, length, data) : Missing(FALSE);
}

extern "C" __declspec(dllexport) BOOL WINAPI GetFileVersionInfoExW(
    DWORD flags, LPCWSTR filename, DWORD handle, DWORD length, LPVOID data)
{
    using Fn = BOOL(WINAPI*)(DWORD, LPCWSTR, DWORD, DWORD, LPVOID);
    const auto fn = Resolve<Fn>("GetFileVersionInfoExW");
    return fn ? fn(flags, filename, handle, length, data) : Missing(FALSE);
}

extern "C" __declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(
    LPCSTR filename, LPDWORD handle)
{
    using Fn = DWORD(WINAPI*)(LPCSTR, LPDWORD);
    const auto fn = Resolve<Fn>("GetFileVersionInfoSizeA");
    return fn ? fn(filename, handle) : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeW(
    LPCWSTR filename, LPDWORD handle)
{
    using Fn = DWORD(WINAPI*)(LPCWSTR, LPDWORD);
    const auto fn = Resolve<Fn>("GetFileVersionInfoSizeW");
    return fn ? fn(filename, handle) : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeExA(
    DWORD flags, LPCSTR filename, LPDWORD handle)
{
    using Fn = DWORD(WINAPI*)(DWORD, LPCSTR, LPDWORD);
    const auto fn = Resolve<Fn>("GetFileVersionInfoSizeExA");
    return fn ? fn(flags, filename, handle) : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeExW(
    DWORD flags, LPCWSTR filename, LPDWORD handle)
{
    using Fn = DWORD(WINAPI*)(DWORD, LPCWSTR, LPDWORD);
    const auto fn = Resolve<Fn>("GetFileVersionInfoSizeExW");
    return fn ? fn(flags, filename, handle) : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) DWORD WINAPI VerFindFileA(
    DWORD flags,
    LPCSTR filename,
    LPCSTR winDir,
    LPCSTR appDir,
    LPSTR currentDir,
    PUINT currentDirLength,
    LPSTR destDir,
    PUINT destDirLength)
{
    using Fn = DWORD(WINAPI*)(DWORD, LPCSTR, LPCSTR, LPCSTR, LPSTR, PUINT, LPSTR, PUINT);
    const auto fn = Resolve<Fn>("VerFindFileA");
    return fn ? fn(flags, filename, winDir, appDir, currentDir, currentDirLength, destDir, destDirLength)
              : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) DWORD WINAPI VerFindFileW(
    DWORD flags,
    LPCWSTR filename,
    LPCWSTR winDir,
    LPCWSTR appDir,
    LPWSTR currentDir,
    PUINT currentDirLength,
    LPWSTR destDir,
    PUINT destDirLength)
{
    using Fn = DWORD(WINAPI*)(DWORD, LPCWSTR, LPCWSTR, LPCWSTR, LPWSTR, PUINT, LPWSTR, PUINT);
    const auto fn = Resolve<Fn>("VerFindFileW");
    return fn ? fn(flags, filename, winDir, appDir, currentDir, currentDirLength, destDir, destDirLength)
              : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) DWORD WINAPI VerInstallFileA(
    DWORD flags,
    LPCSTR srcFilename,
    LPCSTR destFilename,
    LPCSTR srcDir,
    LPCSTR destDir,
    LPCSTR currentDir,
    LPSTR tmpFile,
    PUINT tmpFileLength)
{
    using Fn = DWORD(WINAPI*)(DWORD, LPCSTR, LPCSTR, LPCSTR, LPCSTR, LPCSTR, LPSTR, PUINT);
    const auto fn = Resolve<Fn>("VerInstallFileA");
    return fn ? fn(flags, srcFilename, destFilename, srcDir, destDir, currentDir, tmpFile, tmpFileLength)
              : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) DWORD WINAPI VerInstallFileW(
    DWORD flags,
    LPCWSTR srcFilename,
    LPCWSTR destFilename,
    LPCWSTR srcDir,
    LPCWSTR destDir,
    LPCWSTR currentDir,
    LPWSTR tmpFile,
    PUINT tmpFileLength)
{
    using Fn = DWORD(WINAPI*)(DWORD, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, LPWSTR, PUINT);
    const auto fn = Resolve<Fn>("VerInstallFileW");
    return fn ? fn(flags, srcFilename, destFilename, srcDir, destDir, currentDir, tmpFile, tmpFileLength)
              : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) DWORD WINAPI VerLanguageNameA(
    DWORD language, LPSTR buffer, DWORD bufferLength)
{
    using Fn = DWORD(WINAPI*)(DWORD, LPSTR, DWORD);
    const auto fn = Resolve<Fn>("VerLanguageNameA");
    return fn ? fn(language, buffer, bufferLength) : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) DWORD WINAPI VerLanguageNameW(
    DWORD language, LPWSTR buffer, DWORD bufferLength)
{
    using Fn = DWORD(WINAPI*)(DWORD, LPWSTR, DWORD);
    const auto fn = Resolve<Fn>("VerLanguageNameW");
    return fn ? fn(language, buffer, bufferLength) : Missing<DWORD>(0);
}

extern "C" __declspec(dllexport) BOOL WINAPI VerQueryValueA(
    LPCVOID block, LPCSTR subBlock, LPVOID* buffer, PUINT length)
{
    using Fn = BOOL(WINAPI*)(LPCVOID, LPCSTR, LPVOID*, PUINT);
    const auto fn = Resolve<Fn>("VerQueryValueA");
    return fn ? fn(block, subBlock, buffer, length) : Missing(FALSE);
}

extern "C" __declspec(dllexport) BOOL WINAPI VerQueryValueW(
    LPCVOID block, LPCWSTR subBlock, LPVOID* buffer, PUINT length)
{
    using Fn = BOOL(WINAPI*)(LPCVOID, LPCWSTR, LPVOID*, PUINT);
    const auto fn = Resolve<Fn>("VerQueryValueW");
    return fn ? fn(block, subBlock, buffer, length) : Missing(FALSE);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID)
{
    switch (reason) {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(instance);
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
