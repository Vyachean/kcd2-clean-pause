#include "steam_pause_state_probe.h"
#include "kcd2_abi.h"

#include <MinHook.h>

#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <string>

namespace clean_pause {
namespace {

using namespace kcd2;

constexpr DWORD kWaitForWhGameMs = 60'000;
constexpr DWORD kWaitForFrameworkMs = 120'000;
constexpr DWORD kPollMs = 100;
constexpr DWORD kEscapePollMs = 2;
constexpr DWORD kActiveSampleSleepMs = 1;
constexpr ULONGLONG kActiveSampleWindowMs = 1'000;
constexpr std::uint32_t kSteam156Timestamp = 0x6a350e20;
constexpr std::uint32_t kSteam156ImageSize = 0x05b2d000;
constexpr std::uint32_t kSteam156Checksum = 0x00000000;
constexpr std::size_t kSteam156EnvironmentRva = 0x0492D7F8;
constexpr std::size_t kSteam156FrameworkStorageRva = 0x0549D328;
constexpr std::size_t kSteam156FrameworkVtableRva = 0x040472D0;

HMODULE g_selfModule{};
std::atomic_bool g_stopping{false};
void* g_framework{};
void* g_isGamePausedTarget{};
IsGamePausedFn g_originalIsGamePaused{};
std::atomic_int g_lastPausedState{-1};
std::atomic_uint g_stateChangeCount{0};
SRWLOCK g_logLock = SRWLOCK_INIT;

bool IsReadable(const void* ptr, std::size_t size = 1)
{
    if (!ptr || size == 0)
        return false;

    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(ptr, &mbi, sizeof(mbi)) || mbi.State != MEM_COMMIT)
        return false;
    if ((mbi.Protect & PAGE_GUARD) || (mbi.Protect & PAGE_NOACCESS))
        return false;

    const auto begin = reinterpret_cast<std::uintptr_t>(ptr);
    const auto end = begin + size;
    const auto regionEnd = reinterpret_cast<std::uintptr_t>(mbi.BaseAddress) + mbi.RegionSize;
    return end >= begin && end <= regionEnd;
}

bool IsExecutable(const void* ptr)
{
    if (!ptr)
        return false;

    MEMORY_BASIC_INFORMATION mbi{};
    if (!VirtualQuery(ptr, &mbi, sizeof(mbi)) || mbi.State != MEM_COMMIT)
        return false;

    const DWORD protection = mbi.Protect & 0xff;
    return protection == PAGE_EXECUTE
        || protection == PAGE_EXECUTE_READ
        || protection == PAGE_EXECUTE_READWRITE
        || protection == PAGE_EXECUTE_WRITECOPY;
}

std::wstring LogPath()
{
    wchar_t path[MAX_PATH]{};
    const DWORD length = GetModuleFileNameW(g_selfModule, path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH)
        return L"kcd2_clean_pause_native.log";

    std::wstring result(path, length);
    const auto slash = result.find_last_of(L"\\/");
    if (slash != std::wstring::npos)
        result.resize(slash + 1);
    else
        result.clear();
    result += L"kcd2_clean_pause_native.log";
    return result;
}

void Log(const char* format, ...)
{
    char message[1024]{};
    va_list args;
    va_start(args, format);
    const int count = vsnprintf(message, sizeof(message) - 1, format, args);
    va_end(args);
    if (count <= 0)
        return;

    SYSTEMTIME now{};
    GetLocalTime(&now);
    char line[1280]{};
    const int lineCount = snprintf(
        line,
        sizeof(line) - 1,
        "[%02u:%02u:%02u.%03u] [pause-state-probe] %s\r\n",
        now.wHour,
        now.wMinute,
        now.wSecond,
        now.wMilliseconds,
        message);
    if (lineCount <= 0)
        return;

    AcquireSRWLockExclusive(&g_logLock);
    const std::wstring path = LogPath();
    HANDLE file = CreateFileW(
        path.c_str(),
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file != INVALID_HANDLE_VALUE) {
        DWORD written{};
        WriteFile(file, line, static_cast<DWORD>(lineCount), &written, nullptr);
        CloseHandle(file);
    }
    ReleaseSRWLockExclusive(&g_logLock);
}

bool MatchesSteam156Image(HMODULE whGame)
{
    const auto* base = reinterpret_cast<const std::uint8_t*>(whGame);
    if (!IsReadable(base, sizeof(IMAGE_DOS_HEADER)))
        return false;

    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE)
        return false;

    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (!IsReadable(nt, sizeof(*nt)) || nt->Signature != IMAGE_NT_SIGNATURE)
        return false;

    return nt->FileHeader.TimeDateStamp == kSteam156Timestamp
        && nt->OptionalHeader.SizeOfImage == kSteam156ImageSize
        && nt->OptionalHeader.CheckSum == kSteam156Checksum;
}

bool ResolveVerifiedSteamFramework(HMODULE whGame, void*& framework)
{
    framework = nullptr;
    if (!MatchesSteam156Image(whGame))
        return false;

    auto* imageBase = reinterpret_cast<std::uint8_t*>(whGame);
    auto* environment = imageBase + kSteam156EnvironmentRva;
    auto* storage = imageBase + kSteam156FrameworkStorageRva;
    if (!IsReadable(environment, kEnvSystemOffset + sizeof(void*))
        || !IsReadable(storage, sizeof(void*)))
        return false;

    void* expectedSystem{};
    void* candidate{};
    void** vtable{};
    __try {
        expectedSystem = *reinterpret_cast<void**>(environment + kEnvSystemOffset);
        candidate = *reinterpret_cast<void**>(storage);
        vtable = candidate ? *reinterpret_cast<void***>(candidate) : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (!expectedSystem || !candidate || !vtable
        || vtable != reinterpret_cast<void**>(imageBase + kSteam156FrameworkVtableRva)
        || !IsReadable(vtable, (kGameFrameworkGetSystemSlot + 1) * sizeof(void*)))
        return false;

    const auto getSystem = reinterpret_cast<GameFrameworkGetSystemFn>(
        vtable[kGameFrameworkGetSystemSlot]);
    const auto isGamePaused = reinterpret_cast<IsGamePausedFn>(
        vtable[kGameFrameworkIsGamePausedSlot]);
    if (!IsExecutable(reinterpret_cast<void*>(getSystem))
        || !IsExecutable(reinterpret_cast<void*>(isGamePaused)))
        return false;

    void* actualSystem{};
    __try {
        actualSystem = getSystem(candidate);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    if (actualSystem != expectedSystem)
        return false;

    framework = candidate;
    return true;
}

bool __fastcall HookIsGamePaused(void* framework)
{
    const bool paused = g_originalIsGamePaused(framework);

    if (framework == g_framework) {
        const int next = paused ? 1 : 0;
        const int previous = g_lastPausedState.exchange(next, std::memory_order_acq_rel);
        if (previous != next) {
            const unsigned change = g_stateChangeCount.fetch_add(1, std::memory_order_acq_rel) + 1;
            Log(
                "passive IGameFramework::IsGamePaused state=%s change=%u thread=%lu tick=%llu",
                paused ? "true" : "false",
                change,
                static_cast<unsigned long>(GetCurrentThreadId()),
                static_cast<unsigned long long>(GetTickCount64()));
        }
    }

    return paused;
}

bool InstallObserver(void* framework)
{
    if (!framework || !IsReadable(framework, sizeof(void*)))
        return false;

    void** vtable{};
    __try {
        vtable = *reinterpret_cast<void***>(framework);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    if (!vtable || !IsReadable(vtable, (kGameFrameworkIsGamePausedSlot + 1) * sizeof(void*)))
        return false;

    auto* target = reinterpret_cast<void*>(vtable[kGameFrameworkIsGamePausedSlot]);
    if (!IsExecutable(target))
        return false;

    const MH_STATUS init = MH_Initialize();
    if (init != MH_OK && init != MH_ERROR_ALREADY_INITIALIZED) {
        Log("MH_Initialize failed: %d", static_cast<int>(init));
        return false;
    }

    const MH_STATUS create = MH_CreateHook(
        target,
        reinterpret_cast<void*>(&HookIsGamePaused),
        reinterpret_cast<void**>(&g_originalIsGamePaused));
    if (create != MH_OK) {
        Log("MH_CreateHook(IsGamePaused) failed: %d", static_cast<int>(create));
        return false;
    }

    const MH_STATUS enable = MH_EnableHook(target);
    if (enable != MH_OK) {
        MH_RemoveHook(target);
        g_originalIsGamePaused = nullptr;
        Log("MH_EnableHook(IsGamePaused) failed: %d", static_cast<int>(enable));
        return false;
    }

    g_framework = framework;
    g_isGamePausedTarget = target;
    Log(
        "Steam 1.5.6 IsGamePaused diagnostic observer active; framework=%p slot=%zu target=%p",
        g_framework,
        kGameFrameworkIsGamePausedSlot,
        g_isGamePausedTarget);
    return true;
}

bool ReadPausedStateDirect(bool& paused)
{
    paused = false;
    if (!g_framework || !g_originalIsGamePaused)
        return false;

    __try {
        paused = g_originalIsGamePaused(g_framework);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
}

void RunActiveEscapeSampleWindow()
{
    const ULONGLONG startedAt = GetTickCount64();
    const ULONGLONG deadline = startedAt + kActiveSampleWindowMs;
    int previous = -1;
    unsigned samples{};
    unsigned transitions{};
    bool readFailed{};

    Log(
        "active Escape sampling window started; durationMs=%llu samplerThread=%lu",
        static_cast<unsigned long long>(kActiveSampleWindowMs),
        static_cast<unsigned long>(GetCurrentThreadId()));

    while (!g_stopping.load(std::memory_order_acquire) && GetTickCount64() <= deadline) {
        bool paused{};
        if (!ReadPausedStateDirect(paused)) {
            readFailed = true;
            break;
        }

        ++samples;
        const int next = paused ? 1 : 0;
        if (previous != next) {
            ++transitions;
            Log(
                "active sample state=%s transition=%u sample=%u elapsedMs=%llu",
                paused ? "true" : "false",
                transitions,
                samples,
                static_cast<unsigned long long>(GetTickCount64() - startedAt));
            previous = next;
        }

        Sleep(kActiveSampleSleepMs);
    }

    const ULONGLONG elapsed = GetTickCount64() - startedAt;
    Log(
        "active Escape sampling window complete; samples=%u transitions=%u elapsedMs=%llu avgIntervalMs=%.3f readFailed=%s lastState=%s",
        samples,
        transitions,
        static_cast<unsigned long long>(elapsed),
        samples > 1 ? static_cast<double>(elapsed) / static_cast<double>(samples - 1) : 0.0,
        readFailed ? "true" : "false",
        previous < 0 ? "unavailable" : (previous ? "true" : "false"));
}

void MonitorEscapeAndSample()
{
    bool wasDown = (GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0;
    Log("active Escape pause-state sampler ready; polling physical Escape without changing game input");

    while (!g_stopping.load(std::memory_order_acquire)) {
        const bool down = (GetAsyncKeyState(VK_ESCAPE) & 0x8000) != 0;
        if (down && !wasDown)
            RunActiveEscapeSampleWindow();
        wasDown = down;
        Sleep(kEscapePollMs);
    }
}

DWORD WINAPI ProbeThread(void*)
{
    HMODULE whGame{};
    for (DWORD elapsed = 0; elapsed < kWaitForWhGameMs && !g_stopping.load(); elapsed += kPollMs) {
        whGame = GetModuleHandleW(L"WHGame.dll");
        if (whGame)
            break;
        Sleep(kPollMs);
    }
    if (!whGame || g_stopping.load())
        return 0;

    if (!MatchesSteam156Image(whGame)) {
        Log("Steam pause-state diagnostic disabled: WHGame fingerprint is not the exact supported Steam 1.5.6 build");
        return 0;
    }

    void* framework{};
    for (DWORD elapsed = 0; elapsed < kWaitForFrameworkMs && !g_stopping.load(); elapsed += kPollMs) {
        if (ResolveVerifiedSteamFramework(whGame, framework))
            break;
        Sleep(kPollMs);
    }
    if (!framework || g_stopping.load()) {
        Log("Steam pause-state diagnostic unavailable: verified CCryAction/IGameFramework identity did not become ready");
        return 0;
    }

    if (!InstallObserver(framework))
        return 0;

    bool baseline{};
    if (ReadPausedStateDirect(baseline))
        Log("active sampler baseline IsGamePaused=%s", baseline ? "true" : "false");
    else
        Log("active sampler baseline IsGamePaused read failed");

    MonitorEscapeAndSample();
    return 0;
}

} // namespace

bool StartSteamPauseStateProbe(HMODULE selfModule)
{
    g_selfModule = selfModule;
    g_stopping.store(false, std::memory_order_release);
    g_lastPausedState.store(-1, std::memory_order_release);
    g_stateChangeCount.store(0, std::memory_order_release);

    HANDLE thread = CreateThread(nullptr, 0, ProbeThread, nullptr, 0, nullptr);
    if (!thread)
        return false;
    CloseHandle(thread);
    return true;
}

void StopSteamPauseStateProbe()
{
    g_stopping.store(true, std::memory_order_release);
}

} // namespace clean_pause
