#include "kcd2_runtime_profile.h"
#include "clean_pause_native.h"
#include "clean_pause_blur.h"
#include "clean_pause_bubbles.h"
#include "clean_pause_hud_mask.h"
#include "kcd2_abi.h"

#include <MinHook.h>

#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <initializer_list>
#include <string>

#ifndef CLEAN_PAUSE_VERSION
#define CLEAN_PAUSE_VERSION "unknown"
#endif
#ifndef CLEAN_PAUSE_BUILD_ID
#define CLEAN_PAUSE_BUILD_ID "unknown"
#endif

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
std::atomic_bool g_hudMaskPinSuspended{false};
std::atomic_bool g_hudMaskTransactionAvailable{false};

HMODULE g_selfModule{};
void* g_environment{};
void* g_input{};
void* g_game{};
void* g_gameFramework{};
void* g_flashUI{};
PauseGameFn g_originalPauseGame{};
void* g_pauseGameTarget{};
std::atomic_bool g_pauseBarrierObserved{false};
std::atomic_bool g_pauseTransitionActive{false};
std::atomic_ullong g_pausePressAtMs{0};
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
    bool rootVisible{};
    bool captured{};
};

HudVisibilitySnapshot g_gameplayHudSnapshot{};
HudVisibilitySnapshot g_vanillaPauseHudSnapshot{};
std::atomic_bool g_hudSnapshotRestoreObserved{false};
std::atomic_bool g_hudUpdateThreadMismatchLogged{false};
std::atomic_bool g_hudMaskThreadMismatchLogged{false};
std::atomic_ullong g_nextHudSnapshotRefreshMs{0};
UIElementUpdateFn g_originalHudUpdate{};
void* g_hudUpdateTarget{};
void* g_hudUpdateElement{};
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
    if (!ValidateObjectVtable(value.game, {
            kGameGetLongNameSlot, kGameGetNameSlot, kGameGetFrameworkSlot }))
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

bool LegacyFindRuntimeEnvironment_Xbox156Only(HMODULE whGame, RuntimeEnvironment& result)
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

    // Pending input correlation alone must not mutate/freeze HUD presentation.
    // Only the actual vanilla PauseGame transition and established Clean Pause own
    // this narrow presentation freeze window.
    const bool freeze = g_cleanHidden.load(std::memory_order_acquire)
        || g_pauseTransitionActive.load(std::memory_order_acquire);
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
        MH_RemoveHook(target);
        g_originalHudCallFunction = nullptr;
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
    g_hudMaskThreadMismatchLogged.store(false, std::memory_order_release);
    g_nextHudSnapshotRefreshMs.store(0, std::memory_order_release);
    g_pauseBarrierObserved.store(false, std::memory_order_release);
    g_pauseTransitionActive.store(false, std::memory_order_release);
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
    if (!ValidateObjectVtable(hud, {
            kUIElementGetMovieClipByNameSlot,
            kUIElementIsVisibleSlot,
            kUIElementSetVisibleSlot }))
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
    const auto isRootVisible = VFunc<IsVisibleFn>(hud, kUIElementIsVisibleSlot);
    bool rootVisible{};
    __try {
        rootVisible = isRootVisible && isRootVisible(hud);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    next.rootVisible = rootVisible;

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

    // Root hud@0 visibility is independent from the 28 C_UIHudMask children
    // (wh_ui_ShowHud controls the root). Preserve it exactly instead of forcing HUD on.
    const auto isRootVisible = VFunc<IsVisibleFn>(hud, kUIElementIsVisibleSlot);
    const auto setRootVisible = VFunc<SetVisibleFn>(hud, kUIElementSetVisibleSlot);
    if (!isRootVisible || !setRootVisible
        || !IsExecutable(reinterpret_cast<void*>(isRootVisible))
        || !IsExecutable(reinterpret_cast<void*>(setRootVisible)))
        return false;

    bool currentRootVisible{};
    __try {
        currentRootVisible = isRootVisible(hud);
        if (currentRootVisible && !snapshot.rootVisible)
            setRootVisible(hud, false);
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

    // If the root was hidden, update children while they are not renderable and reveal
    // the container only after the exact child state is in place.
    if (!currentRootVisible && snapshot.rootVisible) {
        __try {
            setRootVisible(hud, true);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            return false;
        }
    }

    if (label && std::strcmp(label, "gameplay") == 0) {
        if (!g_hudSnapshotRestoreObserved.exchange(true, std::memory_order_acq_rel))
            Log("Clean Pause gameplay HUD snapshot restored across all 28 clips");
    } else if (label && std::strcmp(label, "vanilla-pause-visible-menu") == 0) {
        Log("vanilla pause HUD snapshot restored before showing Menu");
    }
    return true;
}

bool ShouldPinGameplayHudPresentation()
{
    if (!g_hudMaskTransactionAvailable.load(std::memory_order_acquire))
        return false;
    if (g_hudMaskPinSuspended.load(std::memory_order_acquire))
        return false;
    if (!g_gameplayHudSnapshot.captured)
        return false;
    if (g_cleanHidden.load(std::memory_order_acquire))
        return true;

    // Do not replay 28 Flash clips during the physical press/release correlation
    // window. Arm transactional pinning only when the verified vanilla PauseGame call
    // itself begins; this keeps the no-blink protection in the mutation call stack
    // without stalling gameplay presentation before the real pause starts.
    return g_pauseTransitionActive.load(std::memory_order_acquire);
}

bool CaptureVanillaHudFromInternalMask(HudVisibilitySnapshot& target)
{
    target = {};
    if (!OnValidatedMainThread("read C_UIHudMask visibility"))
        return false;

    bool visible[kHudClipCount]{};
    if (!g_hudElement
        || !hud_mask::ReadCurrentVisibility(g_hudElement, visible, kHudClipCount))
        return false;

    if (!ValidateObjectVtable(g_hudElement, {kUIElementIsVisibleSlot}))
        return false;
    const auto isRootVisible = VFunc<IsVisibleFn>(g_hudElement, kUIElementIsVisibleSlot);
    bool rootVisible{};
    __try {
        rootVisible = isRootVisible && isRootVisible(g_hudElement);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    for (std::size_t i = 0; i < kHudClipCount; ++i)
        target.visible[i] = visible[i];
    target.rootVisible = rootVisible;
    target.captured = true;
    return true;
}

bool CaptureGameplayHudSnapshot()
{
    // Once the C_UIHudMask transaction has been validated, its internal 28 visibility
    // flags are the authoritative source used by the rest of the transaction. Read
    // those flags directly instead of asking Scaleform for every movieclip's display
    // info synchronously on the physical Pause press. The old Flash walk remains a
    // strict fallback for builds/lifetimes where the internal transaction is absent.
    if (g_hudMaskTransactionAvailable.load(std::memory_order_acquire)) {
        HudVisibilitySnapshot current{};
        if (CaptureVanillaHudFromInternalMask(current)) {
            g_gameplayHudSnapshot = current;
            Log("HUD visibility snapshot captured from C_UIHudMask internal state (gameplay-pre-pause)");
            return true;
        }
        Log("C_UIHudMask gameplay snapshot unavailable; falling back to Flash visibility capture");
    }

    return CaptureHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-pre-pause");
}

bool RestoreVanillaHudPresentation(const char* label)
{
    if (g_hudMaskTransactionAvailable.load(std::memory_order_acquire)) {
        HudVisibilitySnapshot current{};
        if (CaptureVanillaHudFromInternalMask(current)
            && RestoreHudVisibilitySnapshot(current, label))
            return true;
        Log("live C_UIHudMask visibility restore failed (%s)", label ? label : "unnamed");
    }

    if (g_vanillaPauseHudSnapshot.captured)
        return RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, label);
    return false;
}

void FailOpenHudMaskTransaction(
    const HudVisibilitySnapshot* vanillaState,
    const char* reason)
{
    // The original C_UIHudMask mutation has already run. If gameplay replay has not
    // started, current Flash is already vanilla; otherwise use the authoritative
    // internal snapshot captured immediately before that replay. Never continue a
    // transaction whose internal source of truth could not be read.
    g_hudMaskPinSuspended.store(true, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    RestoreBlurBestEffort("HUD-mask transaction fail-open");
    if (vanillaState && vanillaState->captured
        && !RestoreHudVisibilitySnapshot(*vanillaState, "vanilla-mask-fail-open"))
        Log("HUD-mask transaction fail-open could not restore captured vanilla presentation");
    g_cleanHidden.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(0, std::memory_order_release);
    g_swallowPauseRelease.store(false, std::memory_order_release);
    g_swallowResumeRelease.store(false, std::memory_order_release);
    ResetHudSnapshots();
    g_hudMaskPinSuspended.store(false, std::memory_order_release);
    Log("C_UIHudMask transaction fail-open: %s", reason ? reason : "unknown");
}

void ReconcileHudMaskMutation()
{
    // The mask callback can be entered through generic engine dispatch. Validate the
    // thread before touching the non-atomic snapshot structs or mutating Flash.
    if (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId) {
        if (!g_hudMaskThreadMismatchLogged.exchange(true, std::memory_order_acq_rel))
            Log("C_UIHudMask mutation observed off validated main thread; transactional HUD pin skipped");
        return;
    }
    if (!ShouldPinGameplayHudPresentation())
        return;

    // Vanilla has already updated its internal C_UIHudMask state. A fresh complete
    // internal snapshot is mandatory before changing Flash presentation; otherwise
    // fail open while the just-applied vanilla Flash state is still intact.
    HudVisibilitySnapshot vanillaState{};
    if (!CaptureVanillaHudFromInternalMask(vanillaState)) {
        // During an already-active transaction Flash can be a mix of the previously
        // pinned gameplay presentation and the one vanilla element just mutated. Use
        // the last complete internal snapshot if available before relinquishing.
        const HudVisibilitySnapshot fallback = g_vanillaPauseHudSnapshot;
        FailOpenHudMaskTransaction(
            fallback.captured ? &fallback : nullptr,
            "authoritative internal HUD state unavailable");
        return;
    }
    g_vanillaPauseHudSnapshot = vanillaState;

    // Only presentation is rolled back. If that replay itself fails part-way, restore
    // the authoritative vanilla snapshot before releasing Menu rendering.
    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-mask-transaction")) {
        FailOpenHudMaskTransaction(&vanillaState, "gameplay HUD presentation replay failed");
        return;
    }
}

void FailOpenHudMaintenance(const char* reason)
{
    // Relinquish presentation transactionally: first stop all re-pinning paths, then
    // restore the graphics and KCD2's current internal HUD state, and only then allow
    // Menu@0 to render again.
    g_hudMaskPinSuspended.store(true, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    RestoreBlurBestEffort("HUD maintenance fail-open");
    if (!RestoreVanillaHudPresentation("vanilla-pause-fail-open"))
        Log("Clean Pause fail-open could not restore current vanilla HUD presentation");
    g_cleanHidden.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(0, std::memory_order_release);
    ResetHudSnapshots();
    g_hudMaskPinSuspended.store(false, std::memory_order_release);
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

    if (element != g_hudElement)
        return;

    if (GetCurrentThreadId() != g_mainThreadId) {
        if (!g_hudUpdateThreadMismatchLogged.exchange(true, std::memory_order_acq_rel))
            Log("hud@0 Update observed off validated main thread; HUD maintenance disabled for safety");
        return;
    }

    const ULONGLONG now = GetTickCount64();

    // The no-blink transaction starts while pause entry is still pending. If Menu@0
    // never becomes verifiable and no further input arrives, expire that transaction
    // here on the already-proven main-thread HUD update path so gameplay presentation
    // cannot remain pinned indefinitely.
    if (!g_cleanHidden.load(std::memory_order_acquire)) {
        if (g_pendingPauseAttempt.load(std::memory_order_acquire)) {
            const ULONGLONG deadline = g_pendingDeadlineMs.load(std::memory_order_acquire);
            if (deadline != 0 && now > deadline) {
                g_hudMaskPinSuspended.store(true, std::memory_order_release);
                const bool transitionWasActive =
                    g_pauseTransitionActive.exchange(false, std::memory_order_acq_rel);
                g_pendingPauseAttempt.store(false, std::memory_order_release);
                g_pendingDeadlineMs.store(0, std::memory_order_release);
                if (transitionWasActive
                    && g_hudMaskTransactionAvailable.load(std::memory_order_acquire)
                    && g_gameplayHudSnapshot.captured
                    && !RestoreVanillaHudPresentation("vanilla-pending-timeout-update"))
                    Log("pending Clean Pause HUD-update timeout could not restore vanilla presentation");
                ResetHudSnapshots();
                g_hudMaskPinSuspended.store(false, std::memory_order_release);
                Log("pending Clean Pause presentation transaction expired on hud@0 Update");
            }
        }
        return;
    }

    if (g_hudMaskPinSuspended.load(std::memory_order_acquire))
        return;

    const ULONGLONG enteredAt = g_cleanHiddenSinceMs.load(std::memory_order_acquire);
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

    const auto target = reinterpret_cast<void*>(VFunc<UIElementUpdateFn>(hud, kUIElementUpdateSlot));
    if (!target || !IsExecutable(target))
        return false;

    // The expensive listener/RTTI discovery is tied to one concrete hud@0 lifetime.
    // Repeated pause presses on the same HUD reuse the already-validated identities.
    if (g_hudUpdateTarget) {
        if (target != g_hudUpdateTarget)
            return false;
        if (hud == g_hudUpdateElement) {
            g_hudElement = hud;
            return true;
        }
    }

    // C_UIHudMask is the source-derived owner of the 28 child visibility flags.
    // Observe its mutations before vanilla sees Start so a pause-source update can be
    // visually rolled back in the same call stack, before the next render.
    bool maskAvailable = hud_mask::EnsureHooks(hud, &ReconcileHudMaskMutation);
    if (maskAvailable) {
        bool visibilityProbe[kHudClipCount]{};
        maskAvailable = hud_mask::ReadCurrentVisibility(
            hud, visibilityProbe, kHudClipCount);
    }
    g_hudMaskTransactionAvailable.store(maskAvailable, std::memory_order_release);
    if (maskAvailable)
        Log("C_UIHudMask transaction active for hud=%p", hud);
    else
        Log("C_UIHudMask transaction unavailable; using snapshot restore fallback");

    // Overhead NPC subtitles are managed by C_UIHudBubbles below the root "Bubbles"
    // movieclip. Install their optional lifecycle freeze before vanilla sees Start.
    bubbles::EnsureHooks(hud, g_flashUI);

    g_hudElement = hud;
    g_hudUpdateElement = hud;
    if (g_hudUpdateTarget) {
        Log("hud@0 recreated; cached HUD listener identities retargeted to hud=%p", hud);
        return true;
    }

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
        MH_RemoveHook(target);
        g_originalHudUpdate = nullptr;
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
        MH_RemoveHook(renderTarget);
        g_originalRender = nullptr;
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
    g_hudMaskPinSuspended.store(true, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    RestoreBlurBestEffort("clear hidden state");
    if (g_gameplayHudSnapshot.captured
        && !RestoreVanillaHudPresentation("vanilla-current-clear-hidden"))
        Log("Clean Pause clear-hidden could not restore current vanilla HUD presentation");
    g_cleanHidden.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(0, std::memory_order_release);
    g_swallowPauseRelease.store(false, std::memory_order_release);
    g_swallowResumeRelease.store(false, std::memory_order_release);
    ResetHudSnapshots();
    g_hudMaskPinSuspended.store(false, std::memory_order_release);
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

    // A transactional mask callback may already have pinned gameplay presentation
    // before Menu@0 became verifiable. Expiry must restore KCD2's live internal state
    // rather than merely dropping the snapshot bookkeeping.
    g_hudMaskPinSuspended.store(true, std::memory_order_release);
    const bool transitionWasActive =
        g_pauseTransitionActive.exchange(false, std::memory_order_acq_rel);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    if (transitionWasActive && g_gameplayHudSnapshot.captured
        && !RestoreVanillaHudPresentation("vanilla-pending-expiry"))
        Log("pending Clean Pause expiry could not restore current vanilla HUD presentation");
    ResetHudSnapshots();
    g_hudMaskPinSuspended.store(false, std::memory_order_release);
    return false;
}

bool TryEnterCleanPause(
    const char* trigger,
    bool swallowMatchingRelease,
    bool requireMenuVisible = true)
{
    if (requireMenuVisible) {
        bool visible{};
        if (!ReadVerifiedMenuVisible(visible) || !visible)
            return false;
    } else if (!g_menuElement || !g_renderTarget) {
        return false;
    }
    if (!g_gameplayHudSnapshot.captured) {
        ResetHudSnapshots();
        Log("vanilla pause opened but gameplay HUD state was unavailable; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    const bool transactional =
        g_hudMaskTransactionAvailable.load(std::memory_order_acquire);
    if (transactional) {
        // Entry is accepted only with a fresh authoritative internal state. This makes
        // the later visible-menu handoff recoverable even if discovery fails afterwards.
        HudVisibilitySnapshot currentVanilla{};
        if (!CaptureVanillaHudFromInternalMask(currentVanilla)) {
            g_hudMaskPinSuspended.store(true, std::memory_order_release);
            if (g_vanillaPauseHudSnapshot.captured)
                RestoreHudVisibilitySnapshot(
                    g_vanillaPauseHudSnapshot, "vanilla-entry-read-fail-open");
            ResetHudSnapshots();
            g_hudMaskPinSuspended.store(false, std::memory_order_release);
            Log("vanilla pause opened but authoritative C_UIHudMask state could not be read; leaving ordinary visible pause menu (fail-open)");
            return false;
        }
        g_vanillaPauseHudSnapshot = currentVanilla;
    }
    if (!transactional
        && !g_vanillaPauseHudSnapshot.captured
        && !CaptureHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause")) {
        ResetHudSnapshots();
        Log("vanilla pause opened but fallback HUD state could not be captured; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay")) {
        g_hudMaskPinSuspended.store(true, std::memory_order_release);
        RestoreVanillaHudPresentation("vanilla-pause-fail-open");
        ResetHudSnapshots();
        g_hudMaskPinSuspended.store(false, std::memory_order_release);
        Log("vanilla pause opened but gameplay HUD child snapshot could not be restored; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    if (!blur::Disable()) {
        g_hudMaskPinSuspended.store(true, std::memory_order_release);
        RestoreBlurBestEffort("Clean Pause entry rollback");
        RestoreVanillaHudPresentation("vanilla-pause-fail-open");
        ResetHudSnapshots();
        g_hudMaskPinSuspended.store(false, std::memory_order_release);
        Log("vanilla pause opened but DoF blur could not be disabled safely; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    const ULONGLONG enteredAt = GetTickCount64();
    g_hudMaskPinSuspended.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(enteredAt, std::memory_order_release);
    g_nextHudSnapshotRefreshMs.store(enteredAt + kHudSnapshotRefreshIntervalMs, std::memory_order_release);
    g_cleanHidden.store(true, std::memory_order_release);
    g_pauseTransitionActive.store(false, std::memory_order_release);
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
            // Stop the HUD-mask observer from re-pinning gameplay while the saved
            // vanilla pause presentation is being restored. Keep Menu rendering
            // suppressed until that restore is complete, then relinquish ownership.
            g_hudMaskPinSuspended.store(true, std::memory_order_release);
            g_pendingPauseAttempt.store(false, std::memory_order_release);
            g_pendingDeadlineMs.store(0, std::memory_order_release);
            RestoreBlurBestEffort("show vanilla pause via Escape/Start");
            if (!RestoreVanillaHudPresentation("vanilla-pause-visible-menu"))
                Log("could not restore captured vanilla-pause HUD before showing Menu; continuing fail-open");
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            ResetHudSnapshots();
            g_hudMaskPinSuspended.store(false, std::memory_order_release);
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

        g_hudMaskPinSuspended.store(true, std::memory_order_release);
        g_pendingPauseAttempt.store(false, std::memory_order_release);
        g_pendingDeadlineMs.store(0, std::memory_order_release);
        RestoreBlurBestEffort("show vanilla pause via B");
        if (!RestoreVanillaHudPresentation("vanilla-pause-visible-menu-via-B"))
            Log("could not restore captured vanilla-pause HUD before showing Menu via B; continuing fail-open");

        g_cleanHidden.store(false, std::memory_order_release);
        g_renderSuppressionObserved.store(false, std::memory_order_release);
        g_cleanHiddenSinceMs.store(0, std::memory_order_release);
        g_pendingPauseAttempt.store(false, std::memory_order_release);
        g_pendingDeadlineMs.store(0, std::memory_order_release);
        ResetHudSnapshots();
        g_hudMaskPinSuspended.store(false, std::memory_order_release);
        g_swallowResumeRelease.store(true, std::memory_order_release);
        Log("Clean Pause -> visible vanilla pause menu via B (DoF restored; accepted behavior)");
        return;
    }

    // Once a real Menu@0 render has been suppressed, unrelated input is consumed
    // before ActionMapManager so invisible vanilla UI cannot navigate and gameplay /
    // dialogue / cutscene actions cannot leak through.
}

void __fastcall HookPostInputEventCore(void* input, const InputEvent* event, bool force)
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
        const ULONGLONG pressAt = GetTickCount64();
        g_pausePressAtMs.store(pressAt, std::memory_order_release);
        Log("pause physical press: key=%u name=%s state=0x%08x",
            static_cast<unsigned>(key),
            event->keyName ? event->keyName : "<null>",
            static_cast<unsigned>(event->state));
        ResetHudSnapshots();
        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook() || !EnsureHudUpdateHook()
            || !CaptureGameplayHudSnapshot()) {
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
        g_pauseBarrierObserved.store(false, std::memory_order_release);
        const ULONGLONG dispatchAt = GetTickCount64();
        Log("pause press preparation complete; setupMs=%llu",
            static_cast<unsigned long long>(dispatchAt - pressAt));
        Forward(input, event, force);
        Log("pause press vanilla dispatch returned; dispatchMs=%llu",
            static_cast<unsigned long long>(GetTickCount64() - dispatchAt));

        // Preferred path: vanilla itself called and returned from PauseGame(true)
        // while handling this physical press. We are now outside the nested vanilla
        // input stack but still in the same PostInputEvent call, so presentation can
        // be accepted without waiting for the physical Start/Escape release or for a
        // visible Menu frame. The release is swallowed after successful ownership.
        if (g_pauseBarrierObserved.exchange(false, std::memory_order_acq_rel)) {
            if (!TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)
                && g_gameplayHudSnapshot.captured)
                ArmPendingPauseAttempt();
            g_pauseTransitionActive.store(false, std::memory_order_release);
            return;
        }

        // Compatibility fallback when the verified engine barrier was not observed.
        if (!TryEnterCleanPause("Escape/Start press", true)
            && g_gameplayHudSnapshot.captured)
            ArmPendingPauseAttempt();
        return;
    }

    if (released && PendingAttemptAlive()) {
        const ULONGLONG releaseAt = GetTickCount64();
        const ULONGLONG pressAt = g_pausePressAtMs.load(std::memory_order_acquire);
        Log("pause physical release: key=%u sincePressMs=%llu",
            static_cast<unsigned>(key),
            static_cast<unsigned long long>(pressAt ? releaseAt - pressAt : 0));
        Forward(input, event, force);
        const bool barrier =
            g_pauseBarrierObserved.exchange(false, std::memory_order_acq_rel);
        Log("pause release vanilla dispatch returned; dispatchMs=%llu barrier=%s",
            static_cast<unsigned long long>(GetTickCount64() - releaseAt),
            barrier ? "true" : "false");

        bool entered{};
        if (barrier)
            entered = TryEnterCleanPause(
                "vanilla PauseGame barrier after Escape/Start release", false, false);
        else
            entered = TryEnterCleanPause("Escape/Start release", false);
        if (!entered && g_gameplayHudSnapshot.captured)
            ArmPendingPauseAttempt();
        g_pauseTransitionActive.store(false, std::memory_order_release);
        return;
    }

    Forward(input, event, force);
}

bool LegacyResolveGameFramework_Xbox156Only(const RuntimeEnvironment& environment, void*& framework)
{
    framework = nullptr;
    if (!environment.game || !environment.system
        || !ValidateObjectVtable(environment.game, {kGameGetFrameworkSlot}))
        return false;

    const auto getFramework = VFunc<GetGameFrameworkFn>(
        environment.game, kGameGetFrameworkSlot);
    if (!getFramework || !IsExecutable(reinterpret_cast<void*>(getFramework)))
        return false;

    __try {
        framework = getFramework(environment.game);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        framework = nullptr;
    }
    if (!framework || !ValidateObjectVtable(framework, {
            kGameFrameworkPauseGameSlot, kGameFrameworkGetSystemSlot }))
        return false;

    // Identity proof: slot 19 is the verified IGameFramework::GetISystem accessor.
    // Do not hook a merely shape-compatible object whose system does not match gEnv.
    const auto getSystem = VFunc<GameFrameworkGetSystemFn>(
        framework, kGameFrameworkGetSystemSlot);
    void* frameworkSystem{};
    __try {
        frameworkSystem = getSystem ? getSystem(framework) : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        frameworkSystem = nullptr;
    }
    return frameworkSystem == environment.system;
}

} // namespace

} // namespace clean_pause

namespace clean_pause {
namespace {

constexpr DWORD kProfileSlowPollMs = 1'000;
constexpr ULONGLONG kProfileWaitHeartbeatMs = 30'000;
constexpr std::size_t kSteam156FrameworkStorageRva = 0x0549D328;
constexpr std::size_t kSteam156FrameworkVtableRva = 0x040472D0;

HMODULE g_profileWhGame{};
const kcd2::runtime::BuildProfile* g_activeBuildProfile{};
std::atomic_bool g_visiblePauseGesturePassthrough{false};
std::atomic_bool g_hudRootVisibilitySuppressionLogged{false};
std::atomic_bool g_steamEntryRenderPrehide{false};

bool ThreadBelongsToCurrentProcess(DWORD threadId)
{
    if (!threadId)
        return false;

    HANDLE thread = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, threadId);
    if (!thread)
        return false;
    const DWORD ownerProcess = GetProcessIdOfThread(thread);
    CloseHandle(thread);
    return ownerProcess != 0 && ownerProcess == GetCurrentProcessId();
}

// The Xbox retail path already proved the legacy IGame[16] lookup in-game. Keep
// that accepted behavior isolated to Xbox rather than treating slot 16 as a
// storefront-independent IGameFramework accessor.
bool ValidateLegacyXboxGameAndFrameworkIdentity(const RuntimeEnvironment& environment)
{
    if (!environment.game || !environment.system)
        return false;

    using GetGameNameFn = const char*(__fastcall*)(void*);
    if (!ValidateObjectVtable(environment.game, {
            kGameGetNameSlot,
            kGameGetFrameworkSlot }))
        return false;

    const auto getName = VFunc<GetGameNameFn>(environment.game, kGameGetNameSlot);
    const char* gameName{};
    bool nameMatches{};
    __try {
        gameName = getName ? getName(environment.game) : nullptr;
        nameMatches = gameName && std::strcmp(gameName, "kcd2") == 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        nameMatches = false;
    }
    if (!nameMatches)
        return false;

    const auto getFramework = VFunc<GetGameFrameworkFn>(
        environment.game, kGameGetFrameworkSlot);
    if (!getFramework || !IsExecutable(reinterpret_cast<void*>(getFramework)))
        return false;

    void* framework{};
    __try {
        framework = getFramework(environment.game);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        framework = nullptr;
    }
    if (!framework || !ValidateObjectVtable(framework, {
            kGameFrameworkPauseGameSlot,
            kGameFrameworkGetSystemSlot }))
        return false;

    const auto getSystem = VFunc<GameFrameworkGetSystemFn>(
        framework, kGameFrameworkGetSystemSlot);
    void* frameworkSystem{};
    __try {
        frameworkSystem = getSystem ? getSystem(framework) : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        frameworkSystem = nullptr;
    }
    return frameworkSystem == environment.system;
}

bool StronglyValidateEnvironment(RuntimeEnvironment& candidate, RuntimeEnvironment& result)
{
    if (!candidate.base)
        return false;
    if (!ThreadBelongsToCurrentProcess(candidate.mainThreadId))
        return false;
    if (!ValidateLegacyXboxGameAndFrameworkIdentity(candidate))
        return false;

    result = candidate;
    return true;
}

// Exact-profile readiness deliberately validates only capabilities required for
// installing the mature input/menu runtime. PauseGame observation is optional in
// the mature runtime and must not disable Clean Pause when framework discovery is
// unavailable. This restores the original fail-open capability boundary.
const char* ValidateProfileEnvironment(
    const std::uint8_t* environmentBase,
    RuntimeEnvironment& candidate)
{
    candidate = {};
    if (!environmentBase || !IsReadable(environmentBase, kEnvSize))
        return "environment-memory-unreadable";

    __try {
        candidate.base = const_cast<std::uint8_t*>(environmentBase);
        candidate.scriptSystem = *reinterpret_cast<void* const*>(
            environmentBase + kEnvScriptSystemOffset);
        candidate.input = *reinterpret_cast<void* const*>(
            environmentBase + kEnvInputOffset);
        candidate.game = *reinterpret_cast<void* const*>(
            environmentBase + kEnvGameOffset);
        candidate.system = *reinterpret_cast<void* const*>(
            environmentBase + kEnvSystemOffset);
        candidate.flashUI = *reinterpret_cast<void* const*>(
            environmentBase + kEnvFlashUIOffset);
        candidate.mainThreadId = *reinterpret_cast<const DWORD*>(
            environmentBase + kEnvMainThreadIdOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        candidate = {};
        return "environment-field-read-failed";
    }

    if (!candidate.scriptSystem || !candidate.input || !candidate.game
        || !candidate.system || !candidate.flashUI || candidate.mainThreadId == 0)
        return "required-interface-not-ready";
    if (candidate.scriptSystem == candidate.input || candidate.input == candidate.game
        || candidate.game == candidate.system || candidate.system == candidate.flashUI)
        return "environment-interface-alias";

    if (!ValidateObjectVtable(candidate.scriptSystem, {
            kScriptExecuteBufferSlot,
            kScriptGetGlobalAnySlot }))
        return "script-system-vtable";
    if (!ValidateObjectVtable(candidate.input, {kInputPostInputEventSlot}))
        return "input-vtable";
    if (!ValidateObjectVtable(candidate.game, {
            kGameGetLongNameSlot,
            kGameGetNameSlot }))
        return "game-vtable";
    if (!ValidateObjectVtable(candidate.system, {0}))
        return "system-vtable";
    if (!ValidateObjectVtable(candidate.flashUI, {kFlashUIGetElementByInstanceStrSlot}))
        return "flash-ui-vtable";

    HANDLE thread = OpenThread(
        THREAD_QUERY_LIMITED_INFORMATION, FALSE, candidate.mainThreadId);
    if (!thread)
        return "main-thread-unavailable";
    const DWORD ownerProcess = GetProcessIdOfThread(thread);
    CloseHandle(thread);
    if (ownerProcess == 0 || ownerProcess != GetCurrentProcessId())
        return "main-thread-owner-mismatch";

    using GetGameNameFn = const char*(__fastcall*)(void*);
    const auto getName = VFunc<GetGameNameFn>(candidate.game, kGameGetNameSlot);
    const char* gameName{};
    bool nameMatches{};
    __try {
        gameName = getName ? getName(candidate.game) : nullptr;
        // Runtime captures prove different casing across supported retail builds:
        // Xbox returned "kcd2", while Steam 1.5.6 release_1_5-15693 returns "KCD2".
        // Keep the identity gate exact apart from those two observed spellings.
        nameMatches = gameName && (std::strcmp(gameName, "kcd2") == 0
            || std::strcmp(gameName, "KCD2") == 0);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        nameMatches = false;
    }
    if (!nameMatches)
        return "game-name-mismatch";

    return nullptr;
}

bool ResolveSteamFrameworkSingleton(
    const RuntimeEnvironment& environment,
    void*& framework)
{
    framework = nullptr;
    if (!g_profileWhGame || !g_activeBuildProfile
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam
        || !environment.system)
        return false;

    auto* imageBase = reinterpret_cast<std::uint8_t*>(g_profileWhGame);
    auto* storage = imageBase + kSteam156FrameworkStorageRva;
    if (!IsReadable(storage, sizeof(void*)))
        return false;

    __try {
        framework = *reinterpret_cast<void**>(storage);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        framework = nullptr;
    }
    if (!framework || !IsReadable(framework, sizeof(void*)))
        return false;

    void** vtable{};
    __try {
        vtable = *reinterpret_cast<void***>(framework);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        vtable = nullptr;
    }
    if (vtable != reinterpret_cast<void**>(imageBase + kSteam156FrameworkVtableRva))
        return false;
    if (!ValidateObjectVtable(framework, {
            kGameFrameworkPauseGameSlot,
            kGameFrameworkGetSystemSlot }))
        return false;

    const auto getSystem = VFunc<GameFrameworkGetSystemFn>(
        framework, kGameFrameworkGetSystemSlot);
    void* frameworkSystem{};
    __try {
        frameworkSystem = getSystem ? getSystem(framework) : nullptr;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        frameworkSystem = nullptr;
    }
    if (frameworkSystem != environment.system) {
        framework = nullptr;
        return false;
    }
    return true;
}

bool ResolveGameFramework(const RuntimeEnvironment& environment, void*& framework)
{
    framework = nullptr;
    if (g_activeBuildProfile) {
        if (g_activeBuildProfile->storefront == kcd2::runtime::Storefront::Steam)
            return ResolveSteamFrameworkSingleton(environment, framework);

        // GOG/Epic exact environments are valid for the input/menu fallback, but no
        // canonical framework singleton storage has yet been registered for them.
        // Do not reinterpret IGame[16] as IGameFramework on these binaries.
        if (g_activeBuildProfile->storefront != kcd2::runtime::Storefront::XboxMicrosoftStore)
            return false;
    }

    return LegacyResolveGameFramework_Xbox156Only(environment, framework);
}

bool ShouldSuppressSteamHudRootVisibility(bool visible)
{
    if (!g_activeBuildProfile
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam
        || g_hudMaskPinSuspended.load(std::memory_order_acquire)
        || !g_gameplayHudSnapshot.captured)
        return false;

    const bool pin = g_pauseTransitionActive.load(std::memory_order_acquire)
        || g_cleanHidden.load(std::memory_order_acquire);
    if (!pin || visible == g_gameplayHudSnapshot.rootVisible)
        return false;

    if (!g_hudRootVisibilitySuppressionLogged.exchange(true, std::memory_order_acq_rel))
        Log("Steam pause transition suppressed hud@0 root visibility change; preserved gameplay root=%s",
            g_gameplayHudSnapshot.rootVisible ? "visible" : "hidden");
    return true;
}

bool RestoreGameplayHudRootAtPauseBarrier()
{
    if (!g_gameplayHudSnapshot.captured || !g_hudElement
        || (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId)
        || !ValidateObjectVtable(g_hudElement, {
            kUIElementSetVisibleSlot,
            kUIElementIsVisibleSlot }))
        return false;

    const auto isVisible = VFunc<IsVisibleFn>(g_hudElement, kUIElementIsVisibleSlot);
    const auto setVisible = VFunc<SetVisibleFn>(g_hudElement, kUIElementSetVisibleSlot);
    if (!isVisible || !setVisible
        || !IsExecutable(reinterpret_cast<void*>(isVisible))
        || !IsExecutable(reinterpret_cast<void*>(setVisible)))
        return false;

    bool current{};
    __try {
        current = isVisible(g_hudElement);
        if (current != g_gameplayHudSnapshot.rootVisible)
            setVisible(g_hudElement, g_gameplayHudSnapshot.rootVisible);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    if (current != g_gameplayHudSnapshot.rootVisible)
        Log("pause barrier restored gameplay hud@0 root visibility before Clean Pause handoff");
    return true;
}

bool ShouldPrehideSteamEntryRender()
{
    return g_activeBuildProfile
        && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::Steam
        && g_menuElement
        && g_renderTarget
        && g_gameplayHudSnapshot.captured;
}

void RollBackSteamEntryRenderPrehide(const char* reason)
{
    if (!g_steamEntryRenderPrehide.exchange(false, std::memory_order_acq_rel))
        return;
    g_cleanHidden.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(0, std::memory_order_release);
    Log("Steam Clean Pause entry render prehide rolled back (%s)",
        reason ? reason : "handoff not accepted");
}

void __fastcall HookPauseGameProfiled(
    void* framework,
    bool pause,
    bool force,
    unsigned int fadeOutInMs)
{
    const bool observe = framework == g_gameFramework
        && pause
        && g_pendingPauseAttempt.load(std::memory_order_acquire)
        && (!g_mainThreadId || GetCurrentThreadId() == g_mainThreadId);
    const ULONGLONG enteredAt = observe ? GetTickCount64() : 0;

    if (observe) {
        g_pauseTransitionActive.store(true, std::memory_order_release);

        // Menu@0 can render on a different engine/render path while the main thread
        // restores the complete gameplay HUD snapshot. Arm the existing render
        // suppression before the verified vanilla PauseGame(true) call itself. This
        // state is provisional: the PostInputEvent wrapper commits it only if
        // TryEnterCleanPause publishes a real ownership timestamp, otherwise it is
        // rolled back immediately and the ordinary vanilla pause menu remains usable.
        if (ShouldPrehideSteamEntryRender()) {
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_steamEntryRenderPrehide.store(true, std::memory_order_release);
            g_cleanHidden.store(true, std::memory_order_release);
            Log("Steam Clean Pause entry render prehide armed before PauseGame(true)");
        }
    }

    if (!g_originalPauseGame) {
        if (observe) {
            RollBackSteamEntryRenderPrehide("PauseGame trampoline unavailable");
            g_pauseTransitionActive.store(false, std::memory_order_release);
        }
        return;
    }
    g_originalPauseGame(framework, pause, force, fadeOutInMs);

    if (!observe || !g_pendingPauseAttempt.load(std::memory_order_acquire)) {
        if (observe) {
            RollBackSteamEntryRenderPrehide("pending pause correlation ended inside PauseGame");
            g_pauseTransitionActive.store(false, std::memory_order_release);
        }
        return;
    }

    // The shared CFlashUIElement::SetVisible hook pins hud@0 root visibility while
    // PauseGame(true) itself is running. Keep this post-call correction as a cheap
    // defensive check for any root mutation that bypasses SetVisible entirely.
    RestoreGameplayHudRootAtPauseBarrier();

    g_pauseBarrierObserved.store(true, std::memory_order_release);
    const ULONGLONG pressAt = g_pausePressAtMs.load(std::memory_order_acquire);
    Log(
        "vanilla IGameFramework::PauseGame(true) returned during pending pause; force=%s fadeMs=%u callMs=%llu pressToPauseMs=%llu",
        force ? "true" : "false",
        fadeOutInMs,
        static_cast<unsigned long long>(GetTickCount64() - enteredAt),
        static_cast<unsigned long long>(pressAt ? enteredAt - pressAt : 0));
}

bool InstallPauseBarrierHook(
    const RuntimeEnvironment& environment,
    bool logUnavailable)
{
    void* framework{};
    if (!ResolveGameFramework(environment, framework)) {
        if (logUnavailable)
            Log("IGameFramework pause barrier unavailable; continuing with Menu/input fallback");
        return false;
    }

    const auto target = reinterpret_cast<void*>(
        VFunc<PauseGameFn>(framework, kGameFrameworkPauseGameSlot));
    if (!target || !IsExecutable(target))
        return false;

    if (g_pauseGameTarget) {
        if (target != g_pauseGameTarget)
            return false;
        g_gameFramework = framework;
        return true;
    }

    const MH_STATUS create = MH_CreateHook(
        target,
        reinterpret_cast<void*>(&HookPauseGameProfiled),
        reinterpret_cast<void**>(&g_originalPauseGame));
    if (create != MH_OK) {
        Log("MH_CreateHook(IGameFramework::PauseGame) failed: %d", static_cast<int>(create));
        return false;
    }
    const MH_STATUS enable = MH_EnableHook(target);
    if (enable != MH_OK) {
        MH_RemoveHook(target);
        Log("MH_EnableHook(IGameFramework::PauseGame) failed: %d", static_cast<int>(enable));
        return false;
    }

    g_gameFramework = framework;
    g_pauseGameTarget = target;
    Log("vanilla IGameFramework::PauseGame observer active; framework=%p PauseGame=%p",
        g_gameFramework, g_pauseGameTarget);
    return true;
}

bool TryInstallDeferredSteamPauseBarrier()
{
    if (g_pauseGameTarget || !g_activeBuildProfile || !g_environment
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam)
        return g_pauseGameTarget != nullptr;

    RuntimeEnvironment environment{};
    environment.base = g_environment;
    __try {
        environment.system = *reinterpret_cast<void* const*>(
            reinterpret_cast<const std::uint8_t*>(g_environment) + kEnvSystemOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        environment.system = nullptr;
    }
    if (!environment.system)
        return false;

    const bool installed = InstallPauseBarrierHook(environment, false);
    if (installed)
        Log("deferred Steam IGameFramework pause barrier became ready on pause input");
    return installed;
}

bool ShouldTryDeferredSteamPauseBarrier(const InputEvent* event)
{
    if (!event || g_forwardDepth != 0 || g_pauseGameTarget
        || !g_activeBuildProfile
        || g_activeBuildProfile->storefront != kcd2::runtime::Storefront::Steam
        || (g_mainThreadId && GetCurrentThreadId() != g_mainThreadId))
        return false;

    bool shouldTry{};
    __try {
        shouldTry = IsPauseKey(event->keyId)
            && (event->state & InputState::Pressed) != 0;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        shouldTry = false;
    }
    return shouldTry;
}

bool ForwardVisiblePauseGestureIfNeeded(void* input, const InputEvent* event, bool force)
{
    if (!event || g_forwardDepth != 0 || g_cleanHidden.load(std::memory_order_acquire)
        || !IsPauseKey(event->keyId))
        return false;

    const bool pressed = (event->state & InputState::Pressed) != 0;
    const bool released = (event->state & InputState::Released) != 0;

    if (g_visiblePauseGesturePassthrough.load(std::memory_order_acquire)) {
        Forward(input, event, force);
        if (released) {
            g_visiblePauseGesturePassthrough.store(false, std::memory_order_release);
            Log("visible vanilla pause menu Escape/Start gesture passthrough complete");
        }
        return true;
    }

    if (!pressed)
        return false;

    // Check visible Menu@0 before the shared core performs the expensive HUD snapshot.
    // If the render hook has not been established yet, establish only that cheap
    // identity first so an already-open vanilla menu still gets the fast path.
    bool visible{};
    if (!ReadVerifiedMenuVisible(visible)) {
        if (!EnsureMenuRenderHook() || !ReadVerifiedMenuVisible(visible))
            return false;
    }
    if (!visible)
        return false;

    // Latch the whole physical gesture. The first vanilla Pressed closes the menu;
    // subsequent key-repeat Pressed events from the same held key must not become new
    // Clean Pause requests after Menu@0 has disappeared. Release ends the passthrough.
    g_visiblePauseGesturePassthrough.store(true, std::memory_order_release);
    Log("visible vanilla pause menu: forwarding Escape/Start gesture without Clean Pause preparation");
    Forward(input, event, force);
    if (released) {
        g_visiblePauseGesturePassthrough.store(false, std::memory_order_release);
        Log("visible vanilla pause menu Escape/Start gesture passthrough complete");
    }
    return true;
}

void __fastcall HookPostInputEventProfiled(void* input, const InputEvent* event, bool force)
{
    // A visible vanilla pause menu owns Escape/Start completely. Detect that state
    // before Steam barrier acquisition and before the shared core can capture HUD
    // presentation. Keep forwarding repeats until the matching physical release.
    if (ForwardVisiblePauseGestureIfNeeded(input, event, force))
        return;

    // The mature runtime already installs its Menu/HUD/Mask/Bubbles hooks from this
    // same first-Pause call stack, and pinned MinHook serializes its public API.
    // Acquire the optional Steam CCryAction barrier here as well: by real user input
    // the game lifecycle is mature, and avoiding a parallel bootstrap attempt removes
    // a create/enable race against the input thread. Failure stays fail-open and is
    // retried on the next physical Pause press.
    if (ShouldTryDeferredSteamPauseBarrier(event))
        TryInstallDeferredSteamPauseBarrier();

    HookPostInputEventCore(input, event, force);

    // g_cleanHidden is deliberately reused as the already-proven Menu@0 render gate
    // during the short provisional Steam handoff. A successful TryEnterCleanPause sets
    // the ownership timestamp before returning. If that did not happen, clear the
    // provisional gate immediately so fail-open vanilla rendering is never stranded.
    if (g_steamEntryRenderPrehide.exchange(false, std::memory_order_acq_rel)) {
        const bool accepted = g_cleanHidden.load(std::memory_order_acquire)
            && g_cleanHiddenSinceMs.load(std::memory_order_acquire) != 0;
        if (!accepted) {
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            Log("Steam Clean Pause entry render prehide rolled back after input handoff");
        } else {
            Log("Steam Clean Pause entry render prehide committed to Clean Pause ownership");
        }
    }
}

bool InstallInputHook(const RuntimeEnvironment& environment)
{
    g_environment = environment.base;
    g_input = environment.input;
    g_game = environment.game;
    g_flashUI = environment.flashUI;
    g_mainThreadId = environment.mainThreadId;
    blur::Initialize(environment.scriptSystem, environment.mainThreadId);

    // bubbles::EnsureHooks lazily installs the one shared CFlashUIElement::SetVisible
    // detour on the first Pause input. Register the Steam-only hud@0 root filter now,
    // before that lazy installation can occur. Xbox/GOG/Epic behavior stays unchanged.
    bubbles::SetHudRootVisibilityFilter(
        g_activeBuildProfile
            && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::Steam
        ? &ShouldSuppressSteamHudRootVisibility
        : nullptr);

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

    // Install the required input/Menu path first. The PauseGame observer is a
    // strictly optional capability and must never leave a partial runtime behind
    // when the required PostInputEvent hook itself cannot be installed.
    const MH_STATUS create = MH_CreateHook(
        g_postInputEventTarget,
        reinterpret_cast<void*>(&HookPostInputEventProfiled),
        reinterpret_cast<void**>(&g_originalPostInputEvent));
    if (create != MH_OK) {
        Log("MH_CreateHook(PostInputEvent) failed: %d", static_cast<int>(create));
        return false;
    }

    const MH_STATUS enable = MH_EnableHook(g_postInputEventTarget);
    if (enable != MH_OK) {
        MH_RemoveHook(g_postInputEventTarget);
        g_originalPostInputEvent = nullptr;
        Log("MH_EnableHook(PostInputEvent) failed: %d", static_cast<int>(enable));
        return false;
    }

    Log(
        "KCD2 Clean Pause v%s build=%s active; env=%p input=%p game(IGame*)=%p flashUI=%p mainThread=%lu PostInputEvent=%p",
        CLEAN_PAUSE_VERSION,
        CLEAN_PAUSE_BUILD_ID,
        g_environment,
        g_input,
        g_game,
        g_flashUI,
        static_cast<unsigned long>(g_mainThreadId),
        g_postInputEventTarget);

    if (g_activeBuildProfile
        && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::Steam) {
        Log("Steam PauseGame observer will be acquired lazily on the first Pause input; Menu/input runtime is already active");
    } else if (g_activeBuildProfile
        && g_activeBuildProfile->storefront == kcd2::runtime::Storefront::XboxMicrosoftStore) {
        // Preserve the already runtime-tested Xbox behavior. Unlike Steam, there is
        // no second installation path racing this bootstrap attempt.
        InstallPauseBarrierHook(environment, true);
    }
    return true;
}

bool PollRuntimeEnvironment(
    HMODULE whGame,
    const kcd2::runtime::BuildProfile& profile,
    const std::uint8_t* fixedEnvironmentBase,
    RuntimeEnvironment& result,
    RuntimeEnvironment& observedCandidate,
    const char*& failureReason)
{
    result = {};
    observedCandidate = {};
    failureReason = nullptr;
    RuntimeEnvironment candidate{};

    switch (profile.environmentLocator) {
    case kcd2::runtime::EnvironmentLocatorStrategy::LegacyXbox156ValidatedScan:
        if (!LegacyFindRuntimeEnvironment_Xbox156Only(whGame, candidate)) {
            failureReason = "xbox-runtime-not-ready";
            return false;
        }
        observedCandidate = candidate;
        if (!StronglyValidateEnvironment(candidate, result)) {
            failureReason = "xbox-runtime-identity";
            return false;
        }
        return true;

    case kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRva:
    case kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation:
        failureReason = ValidateProfileEnvironment(fixedEnvironmentBase, candidate);
        observedCandidate = candidate;
        if (failureReason)
            return false;
        result = candidate;
        return true;

    default:
        failureReason = "unsupported-locator";
        return false;
    }
}

void LogProfileWaitState(
    const kcd2::runtime::BuildProfile& profile,
    const char* reason,
    const RuntimeEnvironment& candidate,
    const char* prefix)
{
    Log(
        "%s %s runtime readiness: reason=%s env=%p script=%p input=%p game=%p system=%p flashUI=%p mainThread=%lu",
        prefix,
        profile.name,
        reason ? reason : "unknown",
        candidate.base,
        candidate.scriptSystem,
        candidate.input,
        candidate.game,
        candidate.system,
        candidate.flashUI,
        static_cast<unsigned long>(candidate.mainThreadId));
}

DWORD WINAPI BootstrapThread(void*)
{
    Log("native bootstrap started; target=KCD2 Windows retail profiles; KCD2 Clean Pause v%s build=%s",
        CLEAN_PAUSE_VERSION, CLEAN_PAUSE_BUILD_ID);

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

    kcd2::runtime::DetectedBuildIdentity identity{};
    if (!kcd2::runtime::ReadBuildIdentity(whGame, identity)) {
        Log("WHGame build identity unavailable; Clean Pause disabled; no hooks installed");
        return 0;
    }

    Log(
        "WHGame fingerprint: TimeDateStamp=0x%08lx SizeOfImage=0x%08lx CheckSum=0x%08lx",
        static_cast<unsigned long>(identity.fingerprint.timestamp),
        static_cast<unsigned long>(identity.fingerprint.imageSize),
        static_cast<unsigned long>(identity.fingerprint.checksum));
    Log(
        "WHGame metadata: storefront=%s build=%s",
        kcd2::runtime::StorefrontName(identity.storefront),
        identity.buildCode.empty() ? "<unavailable>" : identity.buildCode.c_str());

    const auto* profile = kcd2::runtime::MatchSupportedBuild(identity);
    if (!profile) {
        Log("unsupported WHGame build; Clean Pause disabled; no hooks installed");
        return 0;
    }
    if (!profile->abi || !kcd2::runtime::MatureRuntimeSupports(*profile->abi)) {
        Log("matched build %s selects an ABI unsupported by this Clean Pause runtime; no hooks installed",
            profile->name);
        return 0;
    }

    g_profileWhGame = whGame;
    g_activeBuildProfile = profile;

    Log(
        "WHGame profile candidate: %s; storefront=%s identity=%s abi=%s locator=%s evidence=%s",
        profile->name,
        kcd2::runtime::StorefrontName(profile->storefront),
        kcd2::runtime::BuildIdentityStrategyName(profile->identityStrategy),
        profile->abi->name,
        kcd2::runtime::EnvironmentLocatorName(profile->environmentLocator),
        kcd2::runtime::BuildValidationName(profile->validation));

    std::uint8_t* fixedEnvironmentBase{};
    const bool hasExactEnvironment =
        profile->environmentLocator
            == kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRva
        || profile->environmentLocator
            == kcd2::runtime::EnvironmentLocatorStrategy::ExactEnvironmentRvaWithAnchorValidation;
    if (hasExactEnvironment) {
        if (!kcd2::runtime::ResolveProfileEnvironmentBase(
                whGame, *profile, fixedEnvironmentBase)) {
            Log("matched %s build-level environment identity failed validation; no hooks installed",
                profile->name);
            return 0;
        }
        Log("build-level environment identity validated for %s; env=%p",
            profile->name, fixedEnvironmentBase);
    }

    RuntimeEnvironment environment{};
    if (hasExactEnvironment) {
        const ULONGLONG waitStartedAt = GetTickCount64();
        ULONGLONG lastWaitLogAt{};
        std::string lastReason;

        while (!g_stopping.load()) {
            RuntimeEnvironment candidate{};
            const char* failureReason{};
            if (PollRuntimeEnvironment(
                    whGame,
                    *profile,
                    fixedEnvironmentBase,
                    environment,
                    candidate,
                    failureReason))
                break;

            const ULONGLONG now = GetTickCount64();
            const std::string reason = failureReason ? failureReason : "unknown";
            if (reason != lastReason) {
                LogProfileWaitState(*profile, failureReason, candidate, "waiting for");
                lastReason = reason;
                lastWaitLogAt = now;
            } else if (now - lastWaitLogAt >= kProfileWaitHeartbeatMs) {
                LogProfileWaitState(*profile, failureReason, candidate, "still waiting for");
                lastWaitLogAt = now;
            }

            const DWORD delay = now - waitStartedAt < kWaitForRuntimeMs
                ? kPollMs
                : kProfileSlowPollMs;
            Sleep(delay);
        }
    } else {
        for (DWORD elapsed = 0; elapsed < kWaitForRuntimeMs && !g_stopping.load(); elapsed += kPollMs) {
            RuntimeEnvironment candidate{};
            const char* failureReason{};
            if (PollRuntimeEnvironment(
                    whGame,
                    *profile,
                    fixedEnvironmentBase,
                    environment,
                    candidate,
                    failureReason))
                break;
            Sleep(kPollMs);
        }
    }

    if (g_stopping.load())
        return 0;
    if (!environment.base) {
        Log("matched %s runtime environment could not be validated; no hooks installed",
            profile->name);
        return 0;
    }

    Log("runtime profile validated for %s; env=%p mainThread=%lu",
        profile->name,
        environment.base,
        static_cast<unsigned long>(environment.mainThreadId));
    if (!InstallInputHook(environment))
        Log("Clean Pause hook installation failed for %s; vanilla behavior retained where possible",
            profile->name);
    return 0;
}

} // namespace

bool Start(HMODULE selfModule)
{
    g_selfModule = selfModule;
    g_stopping.store(false, std::memory_order_relaxed);
    g_visiblePauseGesturePassthrough.store(false, std::memory_order_relaxed);
    g_hudRootVisibilitySuppressionLogged.store(false, std::memory_order_relaxed);
    g_steamEntryRenderPrehide.store(false, std::memory_order_relaxed);

    HANDLE thread = CreateThread(nullptr, 0, BootstrapThread, nullptr, 0, nullptr);
    if (!thread)
        return false;
    CloseHandle(thread);
    return true;
}

void Stop()
{
    g_stopping.store(true, std::memory_order_release);
    g_visiblePauseGesturePassthrough.store(false, std::memory_order_release);
    g_steamEntryRenderPrehide.store(false, std::memory_order_release);
    bubbles::SetHudRootVisibilityFilter(nullptr);
}

} // namespace clean_pause
