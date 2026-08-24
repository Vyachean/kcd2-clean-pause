#include "clean_pause_native.h"
#include "kcd2_abi.h"

#include <MinHook.h>

#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <string>

namespace clean_pause {
namespace {

using namespace kcd2;

std::atomic_bool g_stopping{false};
std::atomic_bool g_cleanPaused{false};
std::atomic<std::uint32_t> g_swallowRelease{static_cast<std::uint32_t>(KeyId::None)};

HMODULE g_selfModule{};
void* g_environment{};
void* g_scriptSystem{};
void* g_input{};
void* g_gameFramework{};
DWORD g_mainThreadId{};
PostInputEventFn g_originalPostInputEvent{};
void* g_postInputEventTarget{};
SRWLOCK g_logLock = SRWLOCK_INIT;

constexpr DWORD kWaitForWhGameMs = 60'000;
constexpr DWORD kWaitForRuntimeMs = 120'000;
constexpr DWORD kPollMs = 100;

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
    char message[2048]{};
    va_list args;
    va_start(args, format);
    const int count = vsnprintf(message, sizeof(message) - 1, format, args);
    va_end(args);

    if (count <= 0)
        return;

    SYSTEMTIME now{};
    GetLocalTime(&now);

    char line[2304]{};
    const int lineCount = snprintf(
        line,
        sizeof(line) - 1,
        "[%02u:%02u:%02u.%03u] %s\r\n",
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

bool ValidateObjectVtable(void* object, std::initializer_list<std::size_t> requiredSlots)
{
    if (!IsReadable(object, sizeof(void*)))
        return false;

    void** vtable{};
    __try {
        vtable = *reinterpret_cast<void***>(object);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    std::size_t maxSlot{};
    for (const auto slot : requiredSlots)
        if (slot > maxSlot)
            maxSlot = slot;

    if (!IsReadable(vtable, (maxSlot + 1) * sizeof(void*)))
        return false;

    __try {
        for (const auto slot : requiredSlots) {
            if (!IsExecutable(vtable[slot]))
                return false;
        }
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    return true;
}

struct RuntimeEnvironment {
    void* base{};
    void* scriptSystem{};
    void* input{};
    void* gameFramework{};
    void* system{};
    DWORD mainThreadId{};
};

bool ValidateEnvironmentCandidate(const std::uint8_t* candidate, RuntimeEnvironment& out)
{
    if (!IsReadable(candidate, kEnvSize))
        return false;

    RuntimeEnvironment value{};
    __try {
        value.base = const_cast<std::uint8_t*>(candidate);
        value.scriptSystem = *reinterpret_cast<void* const*>(candidate + kEnvScriptSystemOffset);
        value.input = *reinterpret_cast<void* const*>(candidate + kEnvInputOffset);
        value.gameFramework = *reinterpret_cast<void* const*>(candidate + kEnvGameFrameworkOffset);
        value.system = *reinterpret_cast<void* const*>(candidate + kEnvSystemOffset);
        value.mainThreadId = *reinterpret_cast<const DWORD*>(candidate + kEnvMainThreadIdOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (!value.scriptSystem || !value.input || !value.gameFramework || !value.system || value.mainThreadId == 0)
        return false;

    if (value.scriptSystem == value.input
        || value.input == value.gameFramework
        || value.gameFramework == value.system)
        return false;

    // Requiring exact executable vtable slots makes false-positive environment
    // candidates extremely unlikely and fails open if a future KCD2 build moves
    // the retail ABI. No fixed WHGame.dll RVA is needed for these objects.
    if (!ValidateObjectVtable(value.scriptSystem, {
            kScriptExecuteBufferSlot,
            kScriptReleaseAnySlot,
            kScriptGetGlobalAnySlot,
            kScriptSetGlobalToNullSlot }))
        return false;

    if (!ValidateObjectVtable(value.input, {kInputPostInputEventSlot}))
        return false;

    if (!ValidateObjectVtable(value.gameFramework, {kGameFrameworkPauseGameSlot}))
        return false;

    if (!ValidateObjectVtable(value.system, {0}))
        return false;

    HANDLE thread = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, value.mainThreadId);
    if (!thread)
        return false;
    CloseHandle(thread);

    out = value;
    return true;
}

bool FindRuntimeEnvironment(HMODULE whGame, RuntimeEnvironment& result)
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

    const auto* section = IMAGE_FIRST_SECTION(nt);
    for (unsigned index = 0; index < nt->FileHeader.NumberOfSections; ++index, ++section) {
        const DWORD flags = section->Characteristics;
        if (!(flags & IMAGE_SCN_MEM_READ) || !(flags & IMAGE_SCN_MEM_WRITE))
            continue;

        const auto* start = base + section->VirtualAddress;
        const std::size_t size = section->Misc.VirtualSize;
        if (size < kEnvSize)
            continue;

        const std::size_t limit = size - kEnvSize;
        for (std::size_t offset = 0; offset <= limit; offset += alignof(void*)) {
            RuntimeEnvironment candidate{};
            if (ValidateEnvironmentCandidate(start + offset, candidate)) {
                result = candidate;
                return true;
            }
        }
    }

    return false;
}

bool ExecuteLua(const char* code, const char* description)
{
    if (!g_scriptSystem || !code)
        return false;

    if (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId) {
        Log("refusing Lua call '%s' off the KCD2 main thread", description ? description : "<unnamed>");
        return false;
    }

    const auto execute = VFunc<ExecuteBufferFn>(g_scriptSystem, kScriptExecuteBufferSlot);
    if (!execute)
        return false;

    bool ok{};
    __try {
        ok = execute(
            g_scriptSystem,
            code,
            std::strlen(code),
            description ? description : "@kcd2_clean_pause_native",
            nullptr);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }

    if (!ok)
        Log("Lua execution failed: %s", description ? description : "<unnamed>");
    return ok;
}

bool ReadLuaBoolean(const char* name, bool& value)
{
    if (!g_scriptSystem || !name)
        return false;

    const auto getGlobal = VFunc<GetGlobalAnyFn>(g_scriptSystem, kScriptGetGlobalAnySlot);
    const auto setNull = VFunc<SetGlobalToNullFn>(g_scriptSystem, kScriptSetGlobalToNullSlot);
    const auto release = VFunc<ReleaseAnyFn>(g_scriptSystem, kScriptReleaseAnySlot);
    if (!getGlobal || !setNull || !release)
        return false;

    ScriptAnyValue any{};
    bool ok{};
    __try {
        ok = getGlobal(g_scriptSystem, name, &any);
        if (ok && any.type == ScriptAnyType::Boolean)
            value = any.value.boolean;
        else
            ok = false;

        setNull(g_scriptSystem, name);
        release(g_scriptSystem, &any);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }
    return ok;
}

bool CanEnterCleanPause()
{
    constexpr const char* probe = R"lua(
__kcd2_clean_pause_native_can_enter =
    player ~= nil
    and ActionMapManager ~= nil
    and ActionMapManager.IsFilterEnabled ~= nil
    and not ActionMapManager.IsFilterEnabled("only_ui")
)lua";

    if (!ExecuteLua(probe, "@kcd2_clean_pause_native/probe"))
        return false;

    bool canEnter{};
    if (!ReadLuaBoolean("__kcd2_clean_pause_native_can_enter", canEnter)) {
        Log("could not read gameplay eligibility probe; forwarding vanilla input");
        return false;
    }
    return canEnter;
}

bool SetNativePause(bool paused)
{
    if (!g_gameFramework) {
        Log("IGameFramework unavailable; cannot change native pause state");
        return false;
    }

    if (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId) {
        Log("refusing IGameFramework::PauseGame off the KCD2 main thread");
        return false;
    }

    const auto pause = VFunc<PauseGameFn>(g_gameFramework, kGameFrameworkPauseGameSlot);
    if (!pause || !IsExecutable(reinterpret_cast<const void*>(pause))) {
        Log("IGameFramework::PauseGame vfunc is invalid");
        return false;
    }

    bool ok = true;
    __try {
        // Matches the vanilla ingame-menu primitive: force=true, no fade.
        pause(g_gameFramework, paused, true, 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }

    if (!ok) {
        Log("IGameFramework::PauseGame(%s) raised an exception", paused ? "true" : "false");
        return false;
    }

    Log("IGameFramework::PauseGame(%s, true, 0) invoked", paused ? "true" : "false");
    return true;
}

bool OpenVanillaMenuWhilePaused()
{
    constexpr const char* openMenu = R"lua(
__kcd2_clean_pause_native_menu_opened = false
if UIAction ~= nil
    and UIAction.CallFunction ~= nil
    and ActionMapManager ~= nil
    and ActionMapManager.IsFilterEnabled ~= nil then
    local ok = pcall(function()
        UIAction.CallFunction("MenuEvents", -1, "DisplayIngameMenu", true)
    end)
    __kcd2_clean_pause_native_menu_opened =
        ok and ActionMapManager.IsFilterEnabled("only_ui") == true
end
)lua";

    if (!ExecuteLua(openMenu, "@kcd2_clean_pause_native/open_vanilla_menu"))
        return false;

    bool opened{};
    if (!ReadLuaBoolean("__kcd2_clean_pause_native_menu_opened", opened)) {
        Log("could not verify vanilla pause-menu handoff");
        return false;
    }

    if (!opened)
        Log("MenuEvents.DisplayIngameMenu(true) did not enable only_ui; retaining Clean Pause");
    return opened;
}

bool IsPauseKey(KeyId key)
{
    return key == KeyId::XiStart || key == KeyId::Escape;
}

void Forward(void* input, const InputEvent* event, bool force)
{
    if (g_originalPostInputEvent)
        g_originalPostInputEvent(input, event, force);
}

void __fastcall HookPostInputEvent(void* input, const InputEvent* event, bool force)
{
    if (!event || g_stopping.load(std::memory_order_relaxed)) {
        Forward(input, event, force);
        return;
    }

    const auto key = event->keyId;
    const bool pressed = (event->state & InputState::Pressed) != 0;
    const bool released = (event->state & InputState::Released) != 0;

    const auto releaseToSwallow = static_cast<KeyId>(
        g_swallowRelease.load(std::memory_order_relaxed));
    if (released && releaseToSwallow == key) {
        g_swallowRelease.store(static_cast<std::uint32_t>(KeyId::None), std::memory_order_relaxed);
        return;
    }

    if (g_cleanPaused.load(std::memory_order_acquire)) {
        // While Clean Pause owns the game, no underlying gameplay/dialogue input
        // is forwarded. B resumes; Start/Escape deliberately opens vanilla UI.
        if (pressed && key == KeyId::XiB) {
            if (SetNativePause(false)) {
                g_cleanPaused.store(false, std::memory_order_release);
                g_swallowRelease.store(static_cast<std::uint32_t>(KeyId::XiB), std::memory_order_relaxed);
                Log("Clean Pause -> Running (B consumed)");
            } else {
                Log("resume failed; retaining Clean Pause and consuming B");
            }
            return;
        }

        if (pressed && IsPauseKey(key)) {
            // Keep the simulation paused while the real menu acquires pause/UI
            // ownership. This avoids the old prototype's unpause/re-pause tick.
            if (OpenVanillaMenuWhilePaused()) {
                g_cleanPaused.store(false, std::memory_order_release);
                g_swallowRelease.store(static_cast<std::uint32_t>(key), std::memory_order_relaxed);
                Log("Clean Pause -> vanilla pause menu (no intermediate unpause)");
            }
            return;
        }

        return;
    }

    if (!pressed) {
        Forward(input, event, force);
        return;
    }

    if (!IsPauseKey(key)) {
        Forward(input, event, force);
        return;
    }

    // Never take Start/Escape away from front-end or ordinary full-screen UI.
    // This read-only probe is the only Lua dependency in first-pause routing.
    if (!CanEnterCleanPause()) {
        Forward(input, event, force);
        return;
    }

    if (!SetNativePause(true)) {
        Log("clean-pause acquisition failed; forwarding vanilla pause input");
        Forward(input, event, force);
        return;
    }

    g_cleanPaused.store(true, std::memory_order_release);
    g_swallowRelease.store(static_cast<std::uint32_t>(key), std::memory_order_relaxed);
    Log("Running -> Clean Pause (pause input consumed before ActionMapManager)");
    // The vanilla pause action never sees this press, so no pause-menu frame is
    // emitted by the normal input path.
}

bool InstallHook(const RuntimeEnvironment& environment)
{
    g_environment = environment.base;
    g_scriptSystem = environment.scriptSystem;
    g_input = environment.input;
    g_gameFramework = environment.gameFramework;
    g_mainThreadId = environment.mainThreadId;

    g_postInputEventTarget = reinterpret_cast<void*>(
        VFunc<PostInputEventFn>(g_input, kInputPostInputEventSlot));
    if (!g_postInputEventTarget || !IsExecutable(g_postInputEventTarget)) {
        Log("PostInputEvent vtable target is invalid; native hook not installed");
        return false;
    }

    const MH_STATUS init = MH_Initialize();
    if (init != MH_OK && init != MH_ERROR_ALREADY_INITIALIZED) {
        Log("MH_Initialize failed: %d", static_cast<int>(init));
        return false;
    }

    const MH_STATUS create = MH_CreateHook(
        g_postInputEventTarget,
        reinterpret_cast<void*>(&HookPostInputEvent),
        reinterpret_cast<void**>(&g_originalPostInputEvent));
    if (create != MH_OK) {
        Log("MH_CreateHook(PostInputEvent) failed: %d", static_cast<int>(create));
        return false;
    }

    const MH_STATUS enable = MH_EnableHook(g_postInputEventTarget);
    if (enable != MH_OK) {
        Log("MH_EnableHook(PostInputEvent) failed: %d", static_cast<int>(enable));
        return false;
    }

    Log(
        "native hook active; env=%p script=%p input=%p framework=%p mainThread=%lu PostInputEvent=%p",
        g_environment,
        g_scriptSystem,
        g_input,
        g_gameFramework,
        static_cast<unsigned long>(g_mainThreadId),
        g_postInputEventTarget);
    return true;
}

DWORD WINAPI BootstrapThread(void*)
{
    Log("native bootstrap started; target=KCD2 1.5.6 Windows retail");

    HMODULE whGame{};
    for (DWORD elapsed = 0; elapsed < kWaitForWhGameMs && !g_stopping.load(); elapsed += kPollMs) {
        whGame = GetModuleHandleW(L"WHGame.dll");
        if (whGame)
            break;
        Sleep(kPollMs);
    }

    if (!whGame) {
        Log("WHGame.dll not found; native Clean Pause disabled");
        return 0;
    }

    RuntimeEnvironment environment{};
    for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs && !g_stopping.load(); elapsed += kPollMs) {
        if (FindRuntimeEnvironment(whGame, environment))
            break;
        Sleep(kPollMs);
    }

    if (!environment.base) {
        Log("KCD2 1.5.6 runtime environment / PauseGame ABI could not be validated; no hook installed");
        return 0;
    }

    InstallHook(environment);
    return 0;
}

} // namespace

bool Start(HMODULE selfModule)
{
    g_selfModule = selfModule;
    g_stopping.store(false, std::memory_order_relaxed);

    HANDLE thread = CreateThread(nullptr, 0, BootstrapThread, nullptr, 0, nullptr);
    if (!thread)
        return false;

    CloseHandle(thread);
    return true;
}

void Stop()
{
    // Do not call MinHook teardown under the Windows loader lock. Process
    // termination will discard the address space. This flag makes the worker
    // and hook fall back immediately during detach.
    g_stopping.store(true, std::memory_order_release);
}

} // namespace clean_pause
