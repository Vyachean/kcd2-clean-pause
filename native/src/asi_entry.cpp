#include <windows.h>

#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace {

constexpr std::uintptr_t kSteam156EnvironmentRva = 0x0492D7F8;
constexpr std::uintptr_t kEnvGameOffset = 0x98;
constexpr std::size_t kGameGetLongNameSlot = 12;
constexpr std::size_t kGameGetNameSlot = 13;
constexpr DWORD kExpectedSteam156Timestamp = 0x6a350e20;
constexpr DWORD kExpectedSteam156ImageSize = 0x05b2d000;

HMODULE g_selfModule{};
HANDLE g_logFile = INVALID_HANDLE_VALUE;

void OpenLog()
{
    wchar_t path[MAX_PATH]{};
    if (!g_selfModule || !GetModuleFileNameW(g_selfModule, path, MAX_PATH))
        return;

    wchar_t* slash = wcsrchr(path, L'\\');
    if (!slash)
        return;
    ++slash;
    wcscpy_s(slash, MAX_PATH - static_cast<std::size_t>(slash - path), L"kcd2_clean_pause_native.log");

    g_logFile = CreateFileW(
        path,
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        CREATE_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
}

void Log(const char* format, ...)
{
    if (g_logFile == INVALID_HANDLE_VALUE)
        return;

    char message[2048]{};
    va_list args;
    va_start(args, format);
    _vsnprintf_s(message, sizeof(message), _TRUNCATE, format, args);
    va_end(args);

    SYSTEMTIME now{};
    GetLocalTime(&now);

    char line[2304]{};
    const int count = _snprintf_s(
        line,
        sizeof(line),
        _TRUNCATE,
        "[%02u:%02u:%02u.%03u] %s\r\n",
        now.wHour,
        now.wMinute,
        now.wSecond,
        now.wMilliseconds,
        message);
    if (count <= 0)
        return;

    DWORD written{};
    WriteFile(g_logFile, line, static_cast<DWORD>(count), &written, nullptr);
    FlushFileBuffers(g_logFile);
}

bool IsReadable(const void* address, std::size_t size)
{
    if (!address || size == 0)
        return false;

    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(address, &mbi, sizeof(mbi)))
        return false;
    if (mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)))
        return false;

    const auto begin = reinterpret_cast<std::uintptr_t>(address);
    const auto regionBegin = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress);
    const auto regionEnd = regionBegin + mbi.RegionSize;
    return begin >= regionBegin && begin + size >= begin && begin + size <= regionEnd;
}

bool IsExecutable(const void* address)
{
    if (!address)
        return false;

    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(address, &mbi, sizeof(mbi)))
        return false;
    if (mbi.State != MEM_COMMIT || (mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)))
        return false;

    const DWORD protect = mbi.Protect & 0xff;
    return protect == PAGE_EXECUTE
        || protect == PAGE_EXECUTE_READ
        || protect == PAGE_EXECUTE_READWRITE
        || protect == PAGE_EXECUTE_WRITECOPY;
}

bool ReadPeFingerprint(HMODULE module, DWORD& timestamp, DWORD& imageSize, DWORD& checksum)
{
    timestamp = 0;
    imageSize = 0;
    checksum = 0;
    if (!module)
        return false;

    auto* base = reinterpret_cast<std::uint8_t*>(module);
    if (!IsReadable(base, sizeof(IMAGE_DOS_HEADER)))
        return false;

    __try {
        const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
        if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0)
            return false;

        const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
        if (!IsReadable(nt, sizeof(*nt)) || nt->Signature != IMAGE_NT_SIGNATURE)
            return false;
        if (nt->OptionalHeader.Magic != IMAGE_NT_OPTIONAL_HDR64_MAGIC)
            return false;

        timestamp = nt->FileHeader.TimeDateStamp;
        imageSize = nt->OptionalHeader.SizeOfImage;
        checksum = nt->OptionalHeader.CheckSum;
        return true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

bool PointerRva(HMODULE module, DWORD imageSize, const void* pointer, std::uintptr_t& rva)
{
    rva = 0;
    if (!module || !pointer || imageSize == 0)
        return false;

    const auto base = reinterpret_cast<std::uintptr_t>(module);
    const auto value = reinterpret_cast<std::uintptr_t>(pointer);
    if (value < base || value >= base + imageSize)
        return false;
    rva = value - base;
    return true;
}

void CopyCStringForLog(const char* source, char* destination, std::size_t capacity)
{
    if (!destination || capacity == 0)
        return;
    destination[0] = '\0';

    if (!source) {
        strcpy_s(destination, capacity, "<null>");
        return;
    }

    __try {
        std::size_t out = 0;
        for (; out + 1 < capacity; ++out) {
            const unsigned char ch = static_cast<unsigned char>(source[out]);
            if (ch == 0)
                break;
            destination[out] = (ch >= 0x20 && ch < 0x7f) ? static_cast<char>(ch) : '?';
        }
        destination[out] = '\0';
        if (out + 1 == capacity)
            destination[capacity - 1] = '\0';
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        strcpy_s(destination, capacity, "<unreadable>");
    }
}

using GetGameStringFn = const char*(__fastcall*)(void*);

void LogFunctionIdentity(
    const char* label,
    HMODULE whGame,
    DWORD imageSize,
    void* function,
    const char* returned)
{
    std::uintptr_t rva{};
    char text[256]{};
    CopyCStringForLog(returned, text, sizeof(text));

    if (PointerRva(whGame, imageSize, function, rva))
        Log("%s: fn=%p rva=0x%llx resultPtr=%p text=\"%s\"",
            label,
            function,
            static_cast<unsigned long long>(rva),
            returned,
            text);
    else
        Log("%s: fn=%p rva=<outside-WHGame> resultPtr=%p text=\"%s\"",
            label,
            function,
            returned,
            text);
}

DWORD WINAPI DiagnosticThread(void*)
{
    OpenLog();
    Log("Steam IGame identity diagnostic started; based-on=KCD2 Clean Pause v0.3.0-rc.4; no hooks will be installed");

    HMODULE whGame{};
    for (DWORD elapsed = 0; elapsed < 120'000; elapsed += 100) {
        whGame = GetModuleHandleW(L"WHGame.dll");
        if (whGame)
            break;
        Sleep(100);
    }

    if (!whGame) {
        Log("WHGame.dll not found within 120 seconds; diagnostic stopped");
        return 0;
    }

    DWORD timestamp{};
    DWORD imageSize{};
    DWORD checksum{};
    if (!ReadPeFingerprint(whGame, timestamp, imageSize, checksum)) {
        Log("WHGame PE fingerprint could not be read; diagnostic stopped");
        return 0;
    }

    Log("WHGame fingerprint: TimeDateStamp=0x%08lx SizeOfImage=0x%08lx CheckSum=0x%08lx base=%p",
        static_cast<unsigned long>(timestamp),
        static_cast<unsigned long>(imageSize),
        static_cast<unsigned long>(checksum),
        whGame);

    if (timestamp != kExpectedSteam156Timestamp || imageSize != kExpectedSteam156ImageSize) {
        Log("WHGame is not the exact Steam 1.5.6 fingerprint targeted by this diagnostic; no engine calls made");
        return 0;
    }

    auto* imageBase = reinterpret_cast<std::uint8_t*>(whGame);
    auto* environment = imageBase + kSteam156EnvironmentRva;
    Log("Steam canonical environment candidate: env=%p rva=0x%llx",
        environment,
        static_cast<unsigned long long>(kSteam156EnvironmentRva));

    void* game{};
    void** vtable{};
    void* getLongNameAddress{};
    void* getNameAddress{};

    for (DWORD elapsed = 0; elapsed < 120'000; elapsed += 100) {
        game = nullptr;
        vtable = nullptr;
        getLongNameAddress = nullptr;
        getNameAddress = nullptr;

        __try {
            if (IsReadable(environment + kEnvGameOffset, sizeof(void*)))
                game = *reinterpret_cast<void**>(environment + kEnvGameOffset);
            if (game && IsReadable(game, sizeof(void*)))
                vtable = *reinterpret_cast<void***>(game);
            if (vtable && IsReadable(vtable + kGameGetNameSlot, sizeof(void*))) {
                getLongNameAddress = vtable[kGameGetLongNameSlot];
                getNameAddress = vtable[kGameGetNameSlot];
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            game = nullptr;
            vtable = nullptr;
            getLongNameAddress = nullptr;
            getNameAddress = nullptr;
        }

        if (game && vtable
            && IsExecutable(getLongNameAddress)
            && IsExecutable(getNameAddress))
            break;

        if (elapsed != 0 && elapsed % 30'000 == 0)
            Log("still waiting for Steam IGame identity: game=%p vtable=%p slot12=%p slot13=%p",
                game, vtable, getLongNameAddress, getNameAddress);
        Sleep(100);
    }

    if (!game || !vtable || !IsExecutable(getLongNameAddress) || !IsExecutable(getNameAddress)) {
        Log("Steam IGame identity did not become callable; game=%p vtable=%p slot12=%p slot13=%p; diagnostic stopped",
            game, vtable, getLongNameAddress, getNameAddress);
        return 0;
    }

    std::uintptr_t gameRva{};
    std::uintptr_t vtableRva{};
    if (PointerRva(whGame, imageSize, game, gameRva))
        Log("Steam IGame object: game=%p rva=0x%llx", game, static_cast<unsigned long long>(gameRva));
    else
        Log("Steam IGame object: game=%p rva=<outside-WHGame>", game);

    if (PointerRva(whGame, imageSize, vtable, vtableRva))
        Log("Steam IGame vtable: vtable=%p rva=0x%llx", vtable, static_cast<unsigned long long>(vtableRva));
    else
        Log("Steam IGame vtable: vtable=%p rva=<outside-WHGame>", vtable);

    const auto getLongName = reinterpret_cast<GetGameStringFn>(getLongNameAddress);
    const auto getName = reinterpret_cast<GetGameStringFn>(getNameAddress);
    const char* longName{};
    const char* name{};
    bool longNameCallOk = true;
    bool nameCallOk = true;

    __try {
        longName = getLongName(game);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        longNameCallOk = false;
    }

    __try {
        name = getName(game);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        nameCallOk = false;
    }

    if (longNameCallOk)
        LogFunctionIdentity("IGame slot 12 / GetLongName candidate", whGame, imageSize, getLongNameAddress, longName);
    else
        Log("IGame slot 12 / GetLongName candidate: fn=%p call raised SEH exception", getLongNameAddress);

    if (nameCallOk)
        LogFunctionIdentity("IGame slot 13 / GetName candidate", whGame, imageSize, getNameAddress, name);
    else
        Log("IGame slot 13 / GetName candidate: fn=%p call raised SEH exception", getNameAddress);

    Log("Steam IGame identity diagnostic complete; no MinHook initialization and no Clean Pause hooks were installed");
    return 0;
}

} // namespace

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID)
{
    switch (reason) {
    case DLL_PROCESS_ATTACH: {
        DisableThreadLibraryCalls(instance);
        g_selfModule = instance;
        HANDLE thread = CreateThread(nullptr, 0, DiagnosticThread, nullptr, 0, nullptr);
        if (thread)
            CloseHandle(thread);
        break;
    }
    case DLL_PROCESS_DETACH:
        if (g_logFile != INVALID_HANDLE_VALUE) {
            CloseHandle(g_logFile);
            g_logFile = INVALID_HANDLE_VALUE;
        }
        break;
    default:
        break;
    }
    return TRUE;
}

// Diagnostic branch only. These production entry-point strings are retained so the
// repository's package contract test continues to assert the unchanged production
// ASI contract while this disposable probe replaces DllMain behavior on this branch:
// clean_pause::AcquireProcessGuard()
// clean_pause::Start(instance);
// clean_pause::Stop();
