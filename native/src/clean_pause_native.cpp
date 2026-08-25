#include "clean_pause_native.h"
#include "clean_pause_blur.h"
#include "clean_pause_bubbles.h"
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
std::atomic_ullong g_cleanHiddenSinceMs{0};
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
using HudCallFunctionFn = bool(__fastcall*)(void*, const char*, const void*, void*, const char*);
RenderFn g_originalRender{};
void* g_renderTarget{};
void* g_hudElement{};
HudCallFunctionFn g_originalHudCallFunction{};
void* g_hudCallFunctionTarget{};

constexpr ULONGLONG kHudSnapshotHoldMs = 750;
constexpr ULONGLONG kHudSnapshotRefreshIntervalMs = 75;
constexpr std::size_t kHudClipCount = 28;
constexpr std::size_t kFlashDisplayInfoSize = 0x38;
constexpr std::size_t kFlashDisplayInfoVisibleOffset = 0x28;

const char* const kHudClipNames[kHudClipCount] = {
    "Compass", "Stats", "QAMWeapon", "QAMFood", "Subtitles", "InfoText", "GameLog", "Hints",
    "DialogLeft", "DialogRight", "Cursor", "Crime", "Wanted", "PopUpBackground",
    "TutorialMessage", "FancyEvent", "SkillCheck", "ItemTransfer", "Buffs", "CommonEvent",
    "DiceCursor", "Trespassing", "RatioStrips", "ShootingContest", "Bubbles", "TutorialInDialog",
    "DiceContainer", "Vignette"
};

struct HudVisibilitySnapshot {
    bool visible[kHudClipCount]{};
    bool captured{};
};

HudVisibilitySnapshot g_gameplayHudSnapshot{};
HudVisibilitySnapshot g_vanillaPauseHudSnapshot{};
std::atomic_bool g_hudSnapshotRestoreObserved{false};
std::atomic_bool g_hudUpdateThreadMismatchLogged{false};
std::atomic_ullong g_nextHudSnapshotRefreshMs{0};
UIElementUpdateFn g_originalHudUpdate{};
void* g_hudUpdateTarget{};
std::atomic_bool g_hudUpdateFirstEntryLogged{false};
std::atomic_bool g_hudUpdateFirstReturnLogged{false};
SRWLOCK g_logLock = SRWLOCK_INIT;
thread_local unsigned g_forwardDepth{};

constexpr DWORD kWaitForWhGameMs = 60'000;
constexpr DWORD kWaitForRuntimeMs = 120'000;
constexpr DWORD kPollMs = 100;
constexpr ULONGLONG kPendingWindowMs = 750;
constexpr ULONGLONG kRenderObservationGraceMs = 250;
constexpr std::size_t kUIElementRenderSlot = 24;
constexpr std::size_t kUIElementCallFunctionByNameSlot = 69;

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

void RestoreBlurBestEffort(const char* context)
{
    if (g_forwardDepth != 0)
        return;
    if (!blur::Restore() && blur::IsSuppressed())
        Log("Clean Pause DoF restore failed (%s); will retry on subsequent input",
            context ? context : "unknown");
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

bool ResolveHudElement(void*& hud)
{
    hud = nullptr;
    if (!g_flashUI)
        return false;

    const auto getElement =
        VFunc<GetUIElementByInstanceStrFn>(g_flashUI, kFlashUIGetElementByInstanceStrSlot);
    if (!getElement)
        return false;

    __try {
        hud = getElement(g_flashUI, "hud@0");
        if (!hud)
            hud = getElement(g_flashUI, "HUD@0");
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    return hud && ValidateObjectVtable(hud, {kUIElementCallFunctionByNameSlot});
}

bool ShouldFreezeHudFunction(const char* name)
{
    if (!name)
        return false;

    bool freeze = g_cleanHidden.load(std::memory_order_acquire);
    if (!freeze && g_pendingPauseAttempt.load(std::memory_order_acquire)) {
        const ULONGLONG deadline = g_pendingDeadlineMs.load(std::memory_order_acquire);
        freeze = deadline != 0 && GetTickCount64() <= deadline;
    }
    if (!freeze)
        return false;

    bool block{};
    __try {
        block = std::strcmp(name, "ClearSubtitles") == 0
            || std::strcmp(name, "HideNarrativeSubtitles") == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        block = false;
    }
    return block;
}

bool __fastcall HookHudCallFunction(
    void* element,
    const char* functionName,
    const void* args,
    void* result,
    const char* templateName)
{
    if (element == g_hudElement && ShouldFreezeHudFunction(functionName)) {
        Log("Clean Pause subtitle freeze: suppressed hud.%s", functionName);
        return true;
    }

    return g_originalHudCallFunction
        ? g_originalHudCallFunction(element, functionName, args, result, templateName)
        : false;
}

bool EnsureHudSubtitleHook()
{
    void* hud{};
    if (!ResolveHudElement(hud))
        return false;

    const auto target = reinterpret_cast<void*>(
        VFunc<HudCallFunctionFn>(hud, kUIElementCallFunctionByNameSlot));
    if (!target || !IsExecutable(target))
        return false;

    if (g_hudCallFunctionTarget) {
        if (target != g_hudCallFunctionTarget)
            return false;
        g_hudElement = hud;
        return true;
    }

    g_hudElement = hud;
    const MH_STATUS create = MH_CreateHook(
        target,
        reinterpret_cast<void*>(&HookHudCallFunction),
        reinterpret_cast<void**>(&g_originalHudCallFunction));
    if (create != MH_OK) {
        Log("MH_CreateHook(HUD CallFunction) failed: %d", static_cast<int>(create));
        g_hudElement = nullptr;
        return false;
    }

    const MH_STATUS enable = MH_EnableHook(target);
    if (enable != MH_OK) {
        Log("MH_EnableHook(HUD CallFunction) failed: %d", static_cast<int>(enable));
        g_hudElement = nullptr;
        return false;
    }

    g_hudCallFunctionTarget = target;
    Log("hud@0 subtitle-preservation hook active; hud=%p CallFunction=%p",
        g_hudElement,
        g_hudCallFunctionTarget);
    return true;
}

void ResetHudSnapshots()
{
    g_gameplayHudSnapshot = {};
    g_vanillaPauseHudSnapshot = {};
    g_hudSnapshotRestoreObserved.store(false, std::memory_order_release);
    g_hudUpdateThreadMismatchLogged.store(false, std::memory_order_release);
    g_nextHudSnapshotRefreshMs.store(0, std::memory_order_release);
}

bool OnValidatedMainThread(const char* operation)
{
    if (!g_mainThreadId || GetCurrentThreadId() == g_mainThreadId)
        return true;
    Log("HUD snapshot %s attempted off main thread; refusing Flash mutation", operation ? operation : "operation");
    return false;
}

bool ResolveHudClipAccessor(void*& hud, GetMovieClipByNameFn& getMovieClip)
{
    hud = nullptr;
    getMovieClip = nullptr;
    if (!ResolveHudElement(hud) || hud != g_hudElement)
        return false;
    if (!ValidateObjectVtable(hud, {kUIElementGetMovieClipByNameSlot}))
        return false;
    getMovieClip = VFunc<GetMovieClipByNameFn>(hud, kUIElementGetMovieClipByNameSlot);
    return getMovieClip && IsExecutable(reinterpret_cast<void*>(getMovieClip));
}

bool CaptureHudVisibilitySnapshot(HudVisibilitySnapshot& target, const char* label)
{
    target = {};
    if (!OnValidatedMainThread("capture"))
        return false;

    void* hud{};
    GetMovieClipByNameFn getMovieClip{};
    if (!ResolveHudClipAccessor(hud, getMovieClip))
        return false;

    HudVisibilitySnapshot next{};
    for (std::size_t i = 0; i < kHudClipCount; ++i) {
        void* clip{};
        __try {
            clip = getMovieClip(hud, kHudClipNames[i], nullptr);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            clip = nullptr;
        }

        if (!clip || !ValidateObjectVtable(clip, {
                kFlashVariableGetDisplayInfoSlot,
                kFlashVariableSetVisibleSlot })) {
            Log("HUD snapshot capture unavailable at %s (%s)",
                kHudClipNames[i], label ? label : "unnamed");
            return false;
        }

        alignas(8) unsigned char info[kFlashDisplayInfoSize]{};
        const auto getDisplayInfo = VFunc<FlashVariableGetDisplayInfoFn>(
            clip, kFlashVariableGetDisplayInfoSlot);
        bool ok{};
        __try {
            ok = getDisplayInfo && getDisplayInfo(clip, info);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            ok = false;
        }
        if (!ok) {
            Log("HUD snapshot display state unavailable at %s (%s)",
                kHudClipNames[i], label ? label : "unnamed");
            return false;
        }

        next.visible[i] = info[kFlashDisplayInfoVisibleOffset] != 0;
    }

    next.captured = true;
    target = next;
    Log("HUD visibility snapshot captured for all 28 clips (%s)", label ? label : "unnamed");
    return true;
}

bool RestoreHudVisibilitySnapshot(const HudVisibilitySnapshot& snapshot, const char* label)
{
    if (!snapshot.captured || !OnValidatedMainThread("restore"))
        return false;

    void* hud{};
    GetMovieClipByNameFn getMovieClip{};
    if (!ResolveHudClipAccessor(hud, getMovieClip))
        return false;

    // hud@0 is only the container. RC7d proved its visibility does not control the
    // 28 children, but it still must remain visible for restored child clips to render.
    const auto setRootVisible = VFunc<SetVisibleFn>(hud, kUIElementSetVisibleSlot);
    if (!setRootVisible || !IsExecutable(reinterpret_cast<void*>(setRootVisible)))
        return false;
    __try {
        setRootVisible(hud, true);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    for (std::size_t i = 0; i < kHudClipCount; ++i) {
        void* clip{};
        __try {
            clip = getMovieClip(hud, kHudClipNames[i], nullptr);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            clip = nullptr;
        }
        if (!clip || !ValidateObjectVtable(clip, {
                kFlashVariableSetVisibleSlot })) {
            return false;
        }

        const auto setVisible = VFunc<FlashVariableSetVisibleFn>(
            clip, kFlashVariableSetVisibleSlot);
        bool ok{};
        __try {
            ok = setVisible && setVisible(clip, snapshot.visible[i]);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            ok = false;
        }
        if (!ok)
            return false;
    }

    if (label && std::strcmp(label, "gameplay") == 0) {
        if (!g_hudSnapshotRestoreObserved.exchange(true, std::memory_order_acq_rel))
            Log("Clean Pause gameplay HUD snapshot restored across all 28 clips");
    } else if (label && std::strcmp(label, "vanilla-pause-visible-menu") == 0) {
        Log("vanilla pause HUD snapshot restored before showing Menu");
    }
    return true;
}

void FailOpenHudMaintenance(const char* reason)
{
    // Menu@0 remains logically visible; dropping render suppression is enough to show
    // ordinary vanilla pause. Best-effort restore graphics and HUD state first.
    RestoreBlurBestEffort("HUD maintenance fail-open");
    if (g_vanillaPauseHudSnapshot.captured)
        RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-fail-open");
    g_cleanHidden.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(0, std::memory_order_release);
    ResetHudSnapshots();
    Log("Clean Pause HUD maintenance fail-open: %s", reason ? reason : "unknown");
}

void __fastcall HookHudUpdate(void* element, float deltaTime)
{
    if (!g_hudUpdateFirstEntryLogged.exchange(true, std::memory_order_acq_rel))
        Log("hud@0 Update hook first entry; element=%p thread=%lu cleanHidden=%s",
            element, static_cast<unsigned long>(GetCurrentThreadId()),
            g_cleanHidden.load(std::memory_order_acquire) ? "true" : "false");

    if (g_originalHudUpdate)
        g_originalHudUpdate(element, deltaTime);

    if (!g_hudUpdateFirstReturnLogged.exchange(true, std::memory_order_acq_rel))
        Log("hud@0 Update original returned successfully");

    if (element != g_hudElement || !g_cleanHidden.load(std::memory_order_acquire))
        return;

    if (GetCurrentThreadId() != g_mainThreadId) {
        if (!g_hudUpdateThreadMismatchLogged.exchange(true, std::memory_order_acq_rel))
            Log("hud@0 Update observed off validated main thread; periodic HUD restore disabled for safety");
        return;
    }

    const ULONGLONG enteredAt = g_cleanHiddenSinceMs.load(std::memory_order_acquire);
    const ULONGLONG now = GetTickCount64();
    if (!enteredAt || now - enteredAt > kHudSnapshotHoldMs)
        return;

    const ULONGLONG next = g_nextHudSnapshotRefreshMs.load(std::memory_order_acquire);
    if (next && now < next)
        return;
    g_nextHudSnapshotRefreshMs.store(now + kHudSnapshotRefreshIntervalMs, std::memory_order_release);

    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-maintenance"))
        FailOpenHudMaintenance("periodic gameplay HUD snapshot restore failed");
}

bool EnsureHudUpdateHook()
{
    void* hud{};
    if (!ResolveHudElement(hud))
        return false;

    // Overhead NPC subtitles are managed by C_UIHudBubbles below the root "Bubbles"
    // movieclip. Install their optional lifecycle freeze before vanilla sees Start.
    // Discovery failure is intentionally ignored so the proven Clean Pause path remains
    // available even if a storefront/build changes the concrete listener layout.
    bubbles::EnsureHooks(hud, g_flashUI);

    const auto target = reinterpret_cast<void*>(VFunc<UIElementUpdateFn>(hud, kUIElementUpdateSlot));
    if (!target || !IsExecutable(target))
        return false;

    if (g_hudUpdateTarget) {
        if (target != g_hudUpdateTarget)
            return false;
        g_hudElement = hud;
        return true;
    }

    g_hudElement = hud;
    const MH_STATUS create = MH_CreateHook(
        target,
        reinterpret_cast<void*>(&HookHudUpdate),
        reinterpret_cast<void**>(&g_originalHudUpdate));
    if (create != MH_OK) {
        Log("MH_CreateHook(HUD Update) failed: %d", static_cast<int>(create));
        return false;
    }
    const MH_STATUS enable = MH_EnableHook(target);
    if (enable != MH_OK) {
        Log("MH_EnableHook(HUD Update) failed: %d", static_cast<int>(enable));
        return false;
    }

    g_hudUpdateTarget = target;
    Log("hud@0 main-thread Update hook active; hud=%p Update=%p", g_hudElement, g_hudUpdateTarget);
    return true;
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
    RestoreBlurBestEffort("clear hidden state");
    g_cleanHidden.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(0, std::memory_order_release);
    g_swallowPauseRelease.store(false, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    ResetHudSnapshots();
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
    ResetHudSnapshots();
    return false;
}

bool TryEnterCleanPause(const char* trigger, bool swallowMatchingRelease)
{
    bool visible{};
    if (!ReadVerifiedMenuVisible(visible) || !visible)
        return false;
    if (!g_gameplayHudSnapshot.captured
        || !CaptureHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause")) {
        ResetHudSnapshots();
        Log("vanilla pause opened but its HUD child state could not be captured; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay")) {
        RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-fail-open");
        ResetHudSnapshots();
        Log("vanilla pause opened but gameplay HUD child snapshot could not be restored; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    if (!blur::Disable()) {
        RestoreBlurBestEffort("Clean Pause entry rollback");
        RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-fail-open");
        ResetHudSnapshots();
        Log("vanilla pause opened but DoF blur could not be disabled safely; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    const ULONGLONG enteredAt = GetTickCount64();
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(enteredAt, std::memory_order_release);
    g_nextHudSnapshotRefreshMs.store(enteredAt + kHudSnapshotRefreshIntervalMs, std::memory_order_release);
    g_cleanHidden.store(true, std::memory_order_release);
    g_swallowPauseRelease.store(swallowMatchingRelease, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    Log("Running -> Clean Pause candidate: vanilla Menu@0 Render suppressed; DoF disabled (%s)",
        trigger ? trigger : "pause input");
    return true;
}

void HandleHiddenInput(void* input, const InputEvent* event, bool force)
{
    bool visible{};
    if (!ReadVerifiedMenuVisible(visible)) {
        ClearHiddenState("vanilla Menu@0 verification failed; ordinary pause presentation restored");
        Forward(input, event, force);
        return;
    }
    if (!visible) {
        ClearHiddenState("vanilla Menu@0 closed outside Clean Pause");
        Forward(input, event, force);
        return;
    }

    if (!g_renderSuppressionObserved.load(std::memory_order_acquire)) {
        const ULONGLONG enteredAt = g_cleanHiddenSinceMs.load(std::memory_order_acquire);
        const ULONGLONG now = GetTickCount64();
        if (enteredAt != 0 && now - enteredAt > kRenderObservationGraceMs) {
            if (g_vanillaPauseHudSnapshot.captured)
                RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-fail-open");
            ClearHiddenState("Render suppression was not observed within 250 ms; fail-open");
            Forward(input, event, force);
            return;
        }
    }

    const auto key = event->keyId;
    const bool pressed = (event->state & InputState::Pressed) != 0;
    const bool released = (event->state & InputState::Released) != 0;

    if (IsPauseKey(key)) {
        if (released && g_swallowPauseRelease.exchange(false, std::memory_order_acq_rel))
            return;

        if (pressed) {
            RestoreBlurBestEffort("show vanilla pause via Escape/Start");
            if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-visible-menu"))
                Log("could not restore captured vanilla-pause HUD before showing Menu; continuing fail-open");
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            ResetHudSnapshots();
            g_swallowPauseRelease.store(true, std::memory_order_release);
            Log("Clean Pause -> visible vanilla pause menu (DoF restored; second Escape/Start consumed; Render restored)");
            return;
        }
        return;
    }

    if (key == KeyId::XiB) {
        if (released)
            return;
        if (!pressed)
            return;

        RestoreBlurBestEffort("show vanilla pause via B");
        if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-visible-menu-via-B"))
            Log("could not restore captured vanilla-pause HUD before showing Menu via B; continuing fail-open");

        g_cleanHidden.store(false, std::memory_order_release);
        g_renderSuppressionObserved.store(false, std::memory_order_release);
        g_cleanHiddenSinceMs.store(0, std::memory_order_release);
        g_pendingPauseAttempt.store(false, std::memory_order_release);
        g_pendingDeadlineMs.store(0, std::memory_order_release);
        ResetHudSnapshots();
        g_swallowResumeRelease.store(true, std::memory_order_release);
        Log("Clean Pause -> visible vanilla pause menu via B (DoF restored; v0.1.0 behavior)");
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

    // If a previous graphics restore failed transiently, retry whenever execution
    // returns to the validated input path outside Clean Pause.
    if (!g_cleanHidden.load(std::memory_order_acquire) && blur::IsSuppressed())
        RestoreBlurBestEffort("deferred outside-Clean-Pause retry");

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

    if (g_cleanHidden.load(std::memory_order_acquire) && pressed)
        Log("Clean Pause physical input: key=%u name=%s state=0x%08x",
            static_cast<unsigned>(key),
            event->keyName ? event->keyName : "<null>",
            static_cast<unsigned>(event->state));

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
        ResetHudSnapshots();
        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook() || !EnsureHudUpdateHook()
            || !CaptureHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-pre-pause")) {
            g_pendingPauseAttempt.store(false, std::memory_order_release);
            ResetHudSnapshots();
            Log("pause input: Menu/HUD snapshot path unavailable; leaving vanilla behavior untouched");
            Forward(input, event, force);
            return;
        }

        bool visibleBefore{};
        if (!ReadVerifiedMenuVisible(visibleBefore) || visibleBefore) {
            g_pendingPauseAttempt.store(false, std::memory_order_release);
            ResetHudSnapshots();
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
    blur::Initialize(environment.scriptSystem, environment.mainThreadId);

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
        "KCD2 Clean Pause v0.1.0 active; env=%p input=%p game(IGame*)=%p flashUI=%p mainThread=%lu PostInputEvent=%p",
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
    Log("native bootstrap started; target=KCD2 1.5.6 Windows retail; KCD2 Clean Pause v0.1.0");

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