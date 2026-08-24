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
std::atomic_uint32_t g_followupBudget{0};
std::atomic_ullong g_probeDeadlineMs{0};
std::atomic_ullong g_lastFollowupLogMs{0};

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
constexpr ULONGLONG kProbeWindowMs = 10'000;
constexpr ULONGLONG kFollowupMinIntervalMs = 50;
constexpr std::uint32_t kFollowupBudget = 40;

const char* BoolText(bool value)
{
    return value ? "true" : "false";
}

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

    if (!ValidateObjectVtable(value.scriptSystem, {
            kScriptExecuteBufferSlot,
            kScriptReleaseAnySlot,
            kScriptGetGlobalAnySlot,
            kScriptSetGlobalToNullSlot }))
        return false;

    if (!ValidateObjectVtable(value.input, {kInputPostInputEventSlot}))
        return false;

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

    if (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId)
        return false;

    const auto execute = VFunc<ExecuteBufferFn>(g_scriptSystem, kScriptExecuteBufferSlot);
    if (!execute)
        return false;

    bool ok{};
    __try {
        ok = execute(
            g_scriptSystem,
            code,
            std::strlen(code),
            description ? description : "@kcd2_clean_pause_pause_state_probe",
            nullptr);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }
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
__kcd2_clean_pause_probe_has_player = player ~= nil
__kcd2_clean_pause_probe_only_ui =
    ActionMapManager ~= nil
    and ActionMapManager.IsFilterEnabled ~= nil
    and ActionMapManager.IsFilterEnabled("only_ui")
)lua";

    if (!ExecuteLua(probe, "@kcd2_clean_pause_pause_state_probe/read_context"))
        return false;

    return ReadLuaBoolean("__kcd2_clean_pause_probe_has_player", hasPlayer)
        && ReadLuaBoolean("__kcd2_clean_pause_probe_only_ui", onlyUi);
}

struct MenuState {
    bool lookupOk{};
    bool resolved{};
    bool visibilityOk{};
    bool visible{};
    void* element{};
};

MenuState ReadMenuState()
{
    MenuState state{};
    if (!g_flashUI)
        return state;

    const auto getElement =
        VFunc<GetUIElementByInstanceStrFn>(g_flashUI, kFlashUIGetElementByInstanceStrSlot);
    if (!getElement)
        return state;

    __try {
        state.element = getElement(g_flashUI, "Menu@0");
        state.lookupOk = true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return state;
    }

    state.resolved = state.element != nullptr;
    if (!state.resolved || !ValidateObjectVtable(state.element, {kUIElementIsVisibleSlot}))
        return state;

    const auto isVisible = VFunc<IsVisibleFn>(state.element, kUIElementIsVisibleSlot);
    if (!isVisible)
        return state;

    __try {
        state.visible = isVisible(state.element);
        state.visibilityOk = true;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        state.visibilityOk = false;
    }
    return state;
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

void LogSnapshot(const char* phase, const InputEvent* event)
{
    bool hasPlayer{};
    bool onlyUi{};
    const bool contextOk = ReadPauseContext(hasPlayer, onlyUi);
    const MenuState menu = ReadMenuState();

    Log(
        "pause-state snapshot phase=%s thread=%lu key=%u state=0x%08x context_ok=%s has_player=%s only_ui=%s menu_lookup_ok=%s menu_resolved=%s menu_visibility_ok=%s menu_visible=%s menu=%p",
        phase ? phase : "<unknown>",
        static_cast<unsigned long>(GetCurrentThreadId()),
        event ? static_cast<unsigned>(event->keyId) : 0xffffffffu,
        event ? static_cast<unsigned>(event->state) : 0u,
        BoolText(contextOk),
        BoolText(hasPlayer),
        BoolText(onlyUi),
        BoolText(menu.lookupOk),
        BoolText(menu.resolved),
        BoolText(menu.visibilityOk),
        BoolText(menu.visible),
        menu.element);
}

void ArmFollowupProbe()
{
    const ULONGLONG now = GetTickCount64();
    g_followupBudget.store(kFollowupBudget, std::memory_order_release);
    g_probeDeadlineMs.store(now + kProbeWindowMs, std::memory_order_release);
    g_lastFollowupLogMs.store(0, std::memory_order_release);
}

void MaybeLogFollowup(const InputEvent* event)
{
    auto budget = g_followupBudget.load(std::memory_order_acquire);
    if (budget == 0)
        return;

    const ULONGLONG now = GetTickCount64();
    if (now > g_probeDeadlineMs.load(std::memory_order_acquire)) {
        g_followupBudget.store(0, std::memory_order_release);
        return;
    }

    const ULONGLONG last = g_lastFollowupLogMs.load(std::memory_order_acquire);
    if (last != 0 && now - last < kFollowupMinIntervalMs)
        return;

    if (!g_followupBudget.compare_exchange_strong(
            budget,
            budget - 1,
            std::memory_order_acq_rel,
            std::memory_order_acquire))
        return;

    g_lastFollowupLogMs.store(now, std::memory_order_release);
    LogSnapshot("followup-after-forward", event);
}

void __fastcall HookPostInputEvent(void* input, const InputEvent* event, bool force)
{
    if (!event || g_stopping.load(std::memory_order_relaxed)) {
        Forward(input, event, force);
        return;
    }

    const bool pauseKey = IsPauseKey(event->keyId);
    const bool pressed = (event->state & InputState::Pressed) != 0;
    const bool released = (event->state & InputState::Released) != 0;

    if (pauseKey && pressed) {
        ArmFollowupProbe();
        LogSnapshot("pause-press-before-forward", event);
        Forward(input, event, force);
        LogSnapshot("pause-press-after-forward", event);
        return;
    }

    if (pauseKey && released) {
        LogSnapshot("pause-release-before-forward", event);
        Forward(input, event, force);
        LogSnapshot("pause-release-after-forward", event);
        return;
    }

    // Diagnostic invariant: every non-null physical event is always delivered to
    // KCD2 exactly once. This probe never hides UI, pauses/unpauses, remaps input,
    // enables filters, or consumes an event.
    Forward(input, event, force);
    MaybeLogFollowup(event);
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
        Log("PostInputEvent vtable target is invalid; diagnostic hook not installed");
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
        "rc6 pause-state diagnostic hook active; vanilla input untouched; env=%p script=%p input=%p game(IGame*)=%p flashUI=%p mainThread=%lu PostInputEvent=%p",
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
    Log("native bootstrap started; target=KCD2 1.5.6 Windows retail; rc6 vanilla pause-state diagnostic");

    HMODULE whGame{};
    for (DWORD elapsed = 0; elapsed < kWaitForWhGameMs && !g_stopping.load(); elapsed += kPollMs) {
        whGame = GetModuleHandleW(L"WHGame.dll");
        if (whGame)
            break;
        Sleep(kPollMs);
    }

    if (!whGame) {
        Log("WHGame.dll not found; diagnostic disabled");
        return 0;
    }

    RuntimeEnvironment environment{};
    for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs && !g_stopping.load(); elapsed += kPollMs) {
        if (FindRuntimeEnvironment(whGame, environment))
            break;
        Sleep(kPollMs);
    }

    if (!environment.base) {
        Log("KCD2 1.5.6 runtime environment could not be validated; no diagnostic hook installed");
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
    g_stopping.store(true, std::memory_order_release);
}

} // namespace clean_pause
