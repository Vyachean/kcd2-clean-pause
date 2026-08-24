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
std::atomic_bool g_cleanHidden{false};
std::atomic_bool g_swallowPauseRelease{false};
std::atomic_bool g_swallowResumeRelease{false};
std::atomic_bool g_pendingPauseAttempt{false};

HMODULE g_selfModule{};
void* g_environment{};
void* g_scriptSystem{};
void* g_input{};
void* g_game{};
void* g_flashUI{};
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
    void* game{};
    void* system{};
    void* flashUI{};
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
        value.game = *reinterpret_cast<void* const*>(candidate + kEnvGameOffset);
        value.system = *reinterpret_cast<void* const*>(candidate + kEnvSystemOffset);
        value.flashUI = *reinterpret_cast<void* const*>(candidate + kEnvFlashUIOffset);
        value.mainThreadId = *reinterpret_cast<const DWORD*>(candidate + kEnvMainThreadIdOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (!value.scriptSystem || !value.input || !value.game || !value.system
        || !value.flashUI || value.mainThreadId == 0)
        return false;

    if (value.scriptSystem == value.input
        || value.input == value.game
        || value.game == value.system
        || value.system == value.flashUI)
        return false;

    if (!ValidateObjectVtable(value.scriptSystem, {
            kScriptExecuteBufferSlot,
            kScriptReleaseAnySlot,
            kScriptGetGlobalAnySlot,
            kScriptSetGlobalToNullSlot }))
        return false;

    if (!ValidateObjectVtable(value.input, {kInputPostInputEventSlot}))
        return false;

    // +0x98 is IGame*. These are structural anchors only; no inferred pause ABI
    // is invoked from IGame or IGameFramework.
    if (!ValidateObjectVtable(value.game, {kGameGetLongNameSlot, kGameGetNameSlot}))
        return false;

    if (!ValidateObjectVtable(value.system, {0}))
        return false;

    if (!ValidateObjectVtable(value.flashUI, {kFlashUIGetElementByInstanceStrSlot}))
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
        Log("refusing Lua call '%s' off the KCD2 main thread",
            description ? description : "<unnamed>");
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

bool ReadPauseContext(bool& hasPlayer, bool& onlyUi)
{
    constexpr const char* probe = R"lua(
__kcd2_clean_pause_has_player = player ~= nil
__kcd2_clean_pause_only_ui =
    ActionMapManager ~= nil
    and ActionMapManager.IsFilterEnabled ~= nil
    and ActionMapManager.IsFilterEnabled("only_ui")
)lua";

    if (!ExecuteLua(probe, "@kcd2_clean_pause_native/read_pause_context"))
        return false;

    return ReadLuaBoolean("__kcd2_clean_pause_has_player", hasPlayer)
        && ReadLuaBoolean("__kcd2_clean_pause_only_ui", onlyUi);
}

bool CanAttemptCleanPause()
{
    bool hasPlayer{};
    bool onlyUi{};
    return ReadPauseContext(hasPlayer, onlyUi) && hasPlayer && !onlyUi;
}

bool IsVanillaPauseActive(bool& active)
{
    bool hasPlayer{};
    bool onlyUi{};
    if (!ReadPauseContext(hasPlayer, onlyUi))
        return false;
    active = hasPlayer && onlyUi;
    return true;
}

bool SetMenuVisible(bool visible)
{
    if (!g_flashUI)
        return false;

    const auto getElement =
        VFunc<GetUIElementByInstanceStrFn>(g_flashUI, kFlashUIGetElementByInstanceStrSlot);
    if (!getElement)
        return false;

    void* menu{};
    __try {
        menu = getElement(g_flashUI, "Menu@0");
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (!ValidateObjectVtable(menu, {kUIElementSetVisibleSlot, kUIElementIsVisibleSlot}))
        return false;

    const auto setVisible = VFunc<SetVisibleFn>(menu, kUIElementSetVisibleSlot);
    const auto isVisible = VFunc<IsVisibleFn>(menu, kUIElementIsVisibleSlot);
    if (!setVisible || !isVisible)
        return false;

    bool result{};
    __try {
        setVisible(menu, visible);
        result = isVisible(menu) == visible;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        result = false;
    }
    return result;
}

bool IsPauseKey(KeyId key)
{
    return key == KeyId::Escape || key == KeyId::XiStart;
}

void Forward(void* input, const InputEvent* event, bool force)
{
    if (g_originalPostInputEvent)
        g_originalPostInputEvent(input, event, force);
}

void ClearHiddenState(const char* reason)
{
    g_cleanHidden.store(false, std::memory_order_release);
    g_swallowPauseRelease.store(false, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    if (reason)
        Log("Clean Pause ownership cleared: %s", reason);
}

bool HideVerifiedVanillaPause(const char* trigger)
{
    bool vanillaPaused{};
    if (!IsVanillaPauseActive(vanillaPaused) || !vanillaPaused) {
        Log("%s did not produce verified vanilla only_ui pause; leaving behavior untouched",
            trigger ? trigger : "Escape/Start");
        return false;
    }

    if (!SetMenuVisible(false)) {
        Log("vanilla pause opened but Menu hide failed; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    g_cleanHidden.store(true, std::memory_order_release);
    g_swallowPauseRelease.store(true, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    Log("Running -> Clean Pause: vanilla pause retained, Menu@0 hidden (%s)",
        trigger ? trigger : "pause input");
    return true;
}

void HandleHiddenPauseInput(void* input, const InputEvent* event, bool force)
{
    const auto key = event->keyId;
    const bool pressed = (event->state & InputState::Pressed) != 0;
    const bool released = (event->state & InputState::Released) != 0;

    bool stillPaused{};
    if (!IsVanillaPauseActive(stillPaused) || !stillPaused) {
        SetMenuVisible(true);
        ClearHiddenState("vanilla only_ui no longer active");
        Forward(input, event, force);
        return;
    }

    if (IsPauseKey(key)) {
        if (released && g_swallowPauseRelease.exchange(false, std::memory_order_acq_rel))
            return;

        if (pressed) {
            if (SetMenuVisible(true)) {
                g_cleanHidden.store(false, std::memory_order_release);
                g_swallowPauseRelease.store(true, std::memory_order_release);
                Log("Clean Pause -> visible vanilla pause menu (second Escape/Start consumed)");
                return;
            }

            Log("could not reveal Menu; retaining hidden vanilla pause and consuming Escape/Start");
            return;
        }

        return;
    }

    if (key == KeyId::XiB) {
        // Temporarily reveal the already-open vanilla Menu so its own Back handler
        // can close/unpause it. This all happens inside one input dispatch before
        // the next render, so no menu frame should be exposed.
        if (!SetMenuVisible(true)) {
            Log("could not temporarily reveal Menu for B resume; retaining Clean Pause");
            return;
        }

        Forward(input, event, force);

        bool pausedAfter{};
        if (!IsVanillaPauseActive(pausedAfter)) {
            SetMenuVisible(true);
            Log("could not verify pause state after B; leaving vanilla menu visible (fail-open)");
            ClearHiddenState("pause-state verification failed after B");
            return;
        }

        if (!pausedAfter) {
            g_cleanHidden.store(false, std::memory_order_release);
            if (pressed)
                g_swallowResumeRelease.store(true, std::memory_order_release);
            Log("Clean Pause -> running via vanilla B/back");
            return;
        }

        if (!SetMenuVisible(false)) {
            Log("B did not close vanilla pause and Menu re-hide failed; leaving visible vanilla menu");
            ClearHiddenState("Menu re-hide failed after B");
            return;
        }

        return;
    }

    // While the vanilla pause exists but its Menu is hidden, unrelated input is
    // consumed before ActionMapManager so it cannot navigate invisible UI or leak
    // into gameplay/dialog/cutscene actions.
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

    if (released && key == KeyId::XiB
        && g_swallowResumeRelease.exchange(false, std::memory_order_acq_rel))
        return;

    if (g_cleanHidden.load(std::memory_order_acquire)) {
        HandleHiddenPauseInput(input, event, force);
        return;
    }

    if (!IsPauseKey(key)) {
        Forward(input, event, force);
        return;
    }

    if (released && g_swallowPauseRelease.exchange(false, std::memory_order_acq_rel))
        return;

    if (released && g_pendingPauseAttempt.exchange(false, std::memory_order_acq_rel)) {
        // Some pause contexts may complete their action on release. Forward first,
        // then apply the same verified hide transition.
        Forward(input, event, force);
        HideVerifiedVanillaPause("Escape/Start release");
        return;
    }

    if (!pressed) {
        Forward(input, event, force);
        return;
    }

    // Eligibility is checked before forwarding. The physical Escape/Start event is
    // then delivered to KCD2 unchanged, so the game itself owns every pause counter,
    // audio/dialog/cutscene transition and action-filter change.
    const bool eligible = CanAttemptCleanPause();
    g_pendingPauseAttempt.store(eligible, std::memory_order_release);
    Forward(input, event, force);

    if (!eligible)
        return;

    if (HideVerifiedVanillaPause("Escape/Start press"))
        return;

    // Keep one pending attempt for the matching release. If the press route did
    // nothing, the release is still vanilla and may be the actual menu trigger.
    g_pendingPauseAttempt.store(true, std::memory_order_release);
}

bool InstallHook(const RuntimeEnvironment& environment)
{
    g_environment = environment.base;
    g_scriptSystem = environment.scriptSystem;
    g_input = environment.input;
    g_game = environment.game;
    g_flashUI = environment.flashUI;
    g_mainThreadId = environment.mainThreadId;

    g_postInputEventTarget = reinterpret_cast<void*>(
        VFunc<PostInputEventFn>(g_input, kInputPostInputEventSlot));
    if (!g_postInputEventTarget || !IsExecutable(g_postInputEventTarget)) {
        Log("PostInputEvent vtable target is invalid; hook not installed");
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
        "hidden-vanilla-pause hook active; env=%p script=%p input=%p game(IGame*)=%p flashUI=%p mainThread=%lu PostInputEvent=%p",
        g_environment,
        g_scriptSystem,
        g_input,
        g_game,
        g_flashUI,
        static_cast<unsigned long>(g_mainThreadId),
        g_postInputEventTarget);
    return true;
}

DWORD WINAPI BootstrapThread(void*)
{
    Log("native bootstrap started; target=KCD2 1.5.6 Windows retail; hidden vanilla pause");

    HMODULE whGame{};
    for (DWORD elapsed = 0; elapsed < kWaitForWhGameMs && !g_stopping.load(); elapsed += kPollMs) {
        whGame = GetModuleHandleW(L"WHGame.dll");
        if (whGame)
            break;
        Sleep(kPollMs);
    }

    if (!whGame) {
        Log("WHGame.dll not found; Clean Pause disabled");
        return 0;
    }

    RuntimeEnvironment environment{};
    for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs && !g_stopping.load(); elapsed += kPollMs) {
        if (FindRuntimeEnvironment(whGame, environment))
            break;
        Sleep(kPollMs);
    }

    if (!environment.base) {
        Log("KCD2 1.5.6 runtime environment could not be validated; no hook installed");
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
