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
std::atomic_bool g_renderSuppressionObserved{false};
std::atomic_bool g_swallowPauseRelease{false};
std::atomic_bool g_swallowResumeRelease{false};
std::atomic_bool g_pendingPauseAttempt{false};
std::atomic_ullong g_pendingDeadlineMs{0};

HMODULE g_selfModule{};
void* g_environment{};
void* g_input{};
void* g_game{};
void* g_flashUI{};
DWORD g_mainThreadId{};
void* g_menuElement{};
PostInputEventFn g_originalPostInputEvent{};
void* g_postInputEventTarget{};
using RenderFn = void(__fastcall*)(void*);
RenderFn g_originalRender{};
void* g_renderTarget{};
SRWLOCK g_logLock = SRWLOCK_INIT;
thread_local unsigned g_forwardDepth{};

constexpr DWORD kWaitForWhGameMs = 60'000;
constexpr DWORD kWaitForRuntimeMs = 120'000;
constexpr DWORD kPollMs = 100;
constexpr ULONGLONG kPendingWindowMs = 750;
constexpr std::size_t kUIElementRenderSlot = 24;

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
        for (const auto slot : requiredSlots)
            if (!IsExecutable(vtable[slot]))
                return false;
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
    if (value.scriptSystem == value.input || value.input == value.game
        || value.game == value.system || value.system == value.flashUI)
        return false;

    if (!ValidateObjectVtable(value.scriptSystem, {kScriptExecuteBufferSlot, kScriptGetGlobalAnySlot}))
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

bool ResolveMenuElement(void*& menu)
{
    menu = nullptr;
    if (!g_flashUI)
        return false;

    const auto getElement =
        VFunc<GetUIElementByInstanceStrFn>(g_flashUI, kFlashUIGetElementByInstanceStrSlot);
    if (!getElement)
        return false;

    __try {
        menu = getElement(g_flashUI, "Menu@0");
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    return menu && ValidateObjectVtable(menu, {kUIElementRenderSlot, kUIElementIsVisibleSlot});
}

void __fastcall HookMenuRender(void* element)
{
    if (g_cleanHidden.load(std::memory_order_acquire) && element == g_menuElement) {
        if (!g_renderSuppressionObserved.exchange(true, std::memory_order_acq_rel))
            Log("Clean Pause render suppression observed for Menu@0");
        return;
    }

    if (g_originalRender)
        g_originalRender(element);
}

bool EnsureMenuRenderHook()
{
    void* menu{};
    if (!ResolveMenuElement(menu))
        return false;

    const auto renderTarget = reinterpret_cast<void*>(VFunc<RenderFn>(menu, kUIElementRenderSlot));
    if (!renderTarget || !IsExecutable(renderTarget))
        return false;

    if (g_renderTarget) {
        if (renderTarget != g_renderTarget)
            return false;
        g_menuElement = menu;
        return true;
    }

    g_menuElement = menu;
    const MH_STATUS create = MH_CreateHook(
        renderTarget,
        reinterpret_cast<void*>(&HookMenuRender),
        reinterpret_cast<void**>(&g_originalRender));
    if (create != MH_OK) {
        Log("MH_CreateHook(Menu Render) failed: %d", static_cast<int>(create));
        g_menuElement = nullptr;
        return false;
    }

    const MH_STATUS enable = MH_EnableHook(renderTarget);
    if (enable != MH_OK) {
        Log("MH_EnableHook(Menu Render) failed: %d", static_cast<int>(enable));
        g_menuElement = nullptr;
        return false;
    }

    g_renderTarget = renderTarget;
    Log("Menu@0 render hook active; menu=%p Render=%p", g_menuElement, g_renderTarget);
    return true;
}

bool ReadVerifiedMenuVisible(bool& visible)
{
    visible = false;
    if (!g_menuElement || !g_renderTarget)
        return false;

    void* current{};
    if (!ResolveMenuElement(current) || current != g_menuElement)
        return false;

    const auto renderTarget = reinterpret_cast<void*>(VFunc<RenderFn>(current, kUIElementRenderSlot));
    if (renderTarget != g_renderTarget)
        return false;

    const auto isVisible = VFunc<IsVisibleFn>(current, kUIElementIsVisibleSlot);
    if (!isVisible)
        return false;

    __try {
        visible = isVisible(current);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
}

bool IsPauseKey(KeyId key)
{
    return key == KeyId::Escape || key == KeyId::XiStart;
}

void Forward(void* input, const InputEvent* event, bool force)
{
    if (!g_originalPostInputEvent)
        return;
    ++g_forwardDepth;
    g_originalPostInputEvent(input, event, force);
    --g_forwardDepth;
}

void ClearHiddenState(const char* reason)
{
    g_cleanHidden.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_swallowPauseRelease.store(false, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    if (reason)
        Log("Clean Pause ownership cleared: %s", reason);
}

void ArmPendingPauseAttempt()
{
    g_pendingPauseAttempt.store(true, std::memory_order_release);
    g_pendingDeadlineMs.store(GetTickCount64() + kPendingWindowMs, std::memory_order_release);
}

bool PendingAttemptAlive()
{
    if (!g_pendingPauseAttempt.load(std::memory_order_acquire))
        return false;
    if (GetTickCount64() <= g_pendingDeadlineMs.load(std::memory_order_acquire))
        return true;
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    return false;
}

bool TryEnterCleanPause(const char* trigger, bool swallowMatchingRelease)
{
    bool visible{};
    if (!ReadVerifiedMenuVisible(visible) || !visible)
        return false;

    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHidden.store(true, std::memory_order_release);
    g_swallowPauseRelease.store(swallowMatchingRelease, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    Log("Running -> Clean Pause candidate: vanilla Menu@0 remains visible but its Render is suppressed (%s)",
        trigger ? trigger : "pause input");
    return true;
}

void HandleHiddenInput(void* input, const InputEvent* event, bool force)
{
    bool visible{};
    if (!ReadVerifiedMenuVisible(visible) || !visible) {
        ClearHiddenState("vanilla Menu@0 no longer visible or verification failed");
        Forward(input, event, force);
        return;
    }

    if (!g_renderSuppressionObserved.load(std::memory_order_acquire)) {
        ClearHiddenState("Render suppression was not observed before next physical input; fail-open");
        Forward(input, event, force);
        return;
    }

    const auto key = event->keyId;
    const bool pressed = (event->state & InputState::Pressed) != 0;
    const bool released = (event->state & InputState::Released) != 0;

    if (IsPauseKey(key)) {
        if (released && g_swallowPauseRelease.exchange(false, std::memory_order_acq_rel))
            return;

        if (pressed) {
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_swallowPauseRelease.store(true, std::memory_order_release);
            Log("Clean Pause -> visible vanilla pause menu (second Escape/Start consumed; Render restored)");
            return;
        }
        return;
    }

    if (key == KeyId::XiB) {
        Forward(input, event, force);

        bool visibleAfter{};
        if (!ReadVerifiedMenuVisible(visibleAfter)) {
            ClearHiddenState("Menu visibility verification failed after B; fail-open");
            return;
        }

        if (!visibleAfter) {
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            if (pressed)
                g_swallowResumeRelease.store(true, std::memory_order_release);
            Log("Clean Pause -> running via vanilla B/back");
            return;
        }

        return;
    }

    // Once a real Menu@0 render has been suppressed, unrelated input is consumed
    // before ActionMapManager so invisible vanilla UI cannot navigate and gameplay /
    // dialogue / cutscene actions cannot leak through.
}

void __fastcall HookPostInputEvent(void* input, const InputEvent* event, bool force)
{
    if (!event || g_stopping.load(std::memory_order_relaxed)) {
        Forward(input, event, force);
        return;
    }

    // KCD2 can post nested synthetic input while processing a physical event.
    // Never interpret or consume those nested events: forward them exactly once and
    // make Clean Pause decisions only after the outer vanilla dispatch returns.
    if (g_forwardDepth != 0) {
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
        HandleHiddenInput(input, event, force);
        return;
    }

    if (released && IsPauseKey(key)
        && g_swallowPauseRelease.exchange(false, std::memory_order_acq_rel))
        return;

    if (!IsPauseKey(key)) {
        const bool pending = PendingAttemptAlive();
        Forward(input, event, force);
        if (pending)
            TryEnterCleanPause("delayed follow-up event", false);
        return;
    }

    if (pressed) {
        if (!EnsureMenuRenderHook()) {
            g_pendingPauseAttempt.store(false, std::memory_order_release);
            Log("pause input: Menu@0 render hook unavailable; leaving vanilla behavior untouched");
            Forward(input, event, force);
            return;
        }

        bool visibleBefore{};
        if (!ReadVerifiedMenuVisible(visibleBefore) || visibleBefore) {
            g_pendingPauseAttempt.store(false, std::memory_order_release);
            Forward(input, event, force);
            return;
        }

        ArmPendingPauseAttempt();
        Forward(input, event, force);
        if (!TryEnterCleanPause("Escape/Start press", true))
            ArmPendingPauseAttempt();
        return;
    }

    if (released && PendingAttemptAlive()) {
        Forward(input, event, force);
        if (!TryEnterCleanPause("Escape/Start release", false))
            ArmPendingPauseAttempt();
        return;
    }

    Forward(input, event, force);
}

bool InstallInputHook(const RuntimeEnvironment& environment)
{
    g_environment = environment.base;
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
        "rc7 render-suppression candidate active; env=%p input=%p game(IGame*)=%p flashUI=%p mainThread=%lu PostInputEvent=%p",
        g_environment,
        g_input,
        g_game,
        g_flashUI,
        static_cast<unsigned long>(g_mainThreadId),
        g_postInputEventTarget);
    return true;
}

DWORD WINAPI BootstrapThread(void*)
{
    Log("native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7 render-suppression candidate");

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

    InstallInputHook(environment);
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
