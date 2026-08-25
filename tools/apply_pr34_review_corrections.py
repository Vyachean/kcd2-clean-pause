from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE_PATH = ROOT / "native/src/clean_pause_native.cpp"
MASK_PATH = ROOT / "native/src/clean_pause_hud_mask.cpp"
MASK_H_PATH = ROOT / "native/src/clean_pause_hud_mask.h"
CMAKE_PATH = ROOT / "native/CMakeLists.txt"
TEST_PATH = ROOT / "tests/test_hud_mask_transaction_contract.py"
IDENTITY_TEST_PATH = ROOT / "tests/test_runtime_identity_contract.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, got {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, replacement: str, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f"{label}: start marker missing")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise SystemExit(f"{label}: end marker missing")
    return text[:start_index] + replacement + text[end_index:]


MASK_H_PATH.write_text('''#pragma once

#include <cstddef>

namespace clean_pause::hud_mask {

using MutationObserver = void(*)();
inline constexpr std::size_t kHudElementCount = 28;

// Hooks the concrete KCD2 1.5.6 C_UIHudMask mutation entry points discovered from
// hud@0's listener list by MSVC RTTI. The observer runs immediately after a verified
// vanilla HUD-mask mutation, before control returns to the caller/render.
bool EnsureHooks(void* hudElement, MutationObserver observer);

// Reads KCD2's current source-derived HUD visibility from I_UIHudMask rather than
// from the Flash clips. The caller supplies storage for exactly 28 element values.
// No C_UIHudMask or movieclip pointer is retained by this API.
bool ReadCurrentVisibility(void* hudElement, bool* visible, std::size_t count);

} // namespace clean_pause::hud_mask
''', encoding="utf-8")

mask = MASK_PATH.read_text(encoding="utf-8")
mask = replace_once(
    mask,
    'constexpr std::size_t kMaskSourceMonitorOffset = 0x60;\nconstexpr std::size_t kMaskOnModuleMessageSlot = 3;\nconstexpr std::size_t kSourceEventSlot = 0;',
    'constexpr std::size_t kMaskVisibilityInterfaceOffset = 0x58;\nconstexpr std::size_t kMaskSourceMonitorOffset = 0x60;\nconstexpr std::size_t kMaskOnModuleMessageSlot = 3;\nconstexpr std::size_t kMaskIsElementVisibleSlot = 1;\nconstexpr std::size_t kSourceEventSlot = 0;\nconstexpr std::size_t kModuleMessageIdOffset = 0x08;\nconstexpr std::uint32_t kHudRefreshModuleMessageId = 52;',
    'mask constants',
)
mask = replace_once(
    mask,
    'using SourceEventFn = void(__fastcall*)(void*, void*, bool);\nusing OnModuleMessageFn = void(__fastcall*)(void*, void*);',
    'using SourceEventFn = void(__fastcall*)(void*, void*, bool);\nusing OnModuleMessageFn = void(__fastcall*)(void*, void*);\nusing IsElementVisibleFn = bool(__fastcall*)(void*, std::uint8_t);',
    'mask function types',
)
notify_marker = 'void NotifyAfterMutation()\n{\n'
helper = '''bool IsHudRefreshMessage(const void* message)
{
    if (!IsReadable(message, kModuleMessageIdOffset + sizeof(std::uint32_t)))
        return false;

    std::uint32_t id{};
    __try {
        id = *reinterpret_cast<const std::uint32_t*>(
            reinterpret_cast<const std::uint8_t*>(message) + kModuleMessageIdOffset);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return id == kHudRefreshModuleMessageId;
}

'''
if helper not in mask:
    mask = replace_once(mask, notify_marker, helper + notify_marker, 'module-message filter helper')
mask = replace_once(
    mask,
    '''void __fastcall HookOnModuleMessage(void* mask, void* message)
{
    if (g_originalOnModuleMessage)
        g_originalOnModuleMessage(mask, message);
    NotifyAfterMutation();
}
''',
    '''void __fastcall HookOnModuleMessage(void* mask, void* message)
{
    // All GUI elements receive the general module-message broadcast. C_UIHudMask
    // mutates visibility only for message id 52; read that id before vanilla runs so
    // the message object does not need to outlive the original call.
    const bool refresh = IsHudRefreshMessage(message);
    if (g_originalOnModuleMessage)
        g_originalOnModuleMessage(mask, message);
    if (refresh)
        NotifyAfterMutation();
}
''',
    'OnModuleMessage filter',
)
read_visibility = '''
bool ReadCurrentVisibility(void* hudElement, bool* visible, std::size_t count)
{
    if (!visible || count != kHudElementCount)
        return false;

    void* mask{};
    void* sourceMonitor{};
    if (!FindMaskObjects(hudElement, mask, sourceMonitor))
        return false;

    auto* visibilityInterface = reinterpret_cast<std::uint8_t*>(mask)
        + kMaskVisibilityInterfaceOffset;
    void* interfaceOwner{};
    std::uint32_t interfaceOffset{};
    if (!ResolveCompleteObjectByRtti(
            visibilityInterface, kMaskRttiName, interfaceOwner, interfaceOffset)
        || interfaceOwner != mask || interfaceOffset != kMaskVisibilityInterfaceOffset)
        return false;
    if (!ValidateVtable(visibilityInterface, kMaskIsElementVisibleSlot))
        return false;

    const auto isVisible = VFunc<IsElementVisibleFn>(
        visibilityInterface, kMaskIsElementVisibleSlot);
    if (!isVisible || !IsExecutable(reinterpret_cast<void*>(isVisible)))
        return false;

    __try {
        for (std::size_t i = 0; i < kHudElementCount; ++i)
            visible[i] = isVisible(visibilityInterface, static_cast<std::uint8_t>(i));
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
}
'''
mask = replace_once(
    mask,
    '\n} // namespace clean_pause::hud_mask\n',
    read_visibility + '\n} // namespace clean_pause::hud_mask\n',
    'live mask read API',
)
MASK_PATH.write_text(mask, encoding="utf-8")

native = NATIVE_PATH.read_text(encoding="utf-8")
native = replace_once(
    native,
    '#include <windows.h>\n\nnamespace clean_pause {',
    '#include <windows.h>\n\n#ifndef CLEAN_PAUSE_VERSION\n#define CLEAN_PAUSE_VERSION "unknown"\n#endif\n#ifndef CLEAN_PAUSE_BUILD_ID\n#define CLEAN_PAUSE_BUILD_ID "unknown"\n#endif\n\nnamespace clean_pause {',
    'runtime identity macros',
)
native = replace_once(
    native,
    'std::atomic_bool g_hudMaskPinSuspended{false};',
    'std::atomic_bool g_hudMaskPinSuspended{false};\nstd::atomic_bool g_hudMaskTransactionAvailable{false};',
    'transaction availability state',
)
native = replace_once(
    native,
    'std::atomic_bool g_hudUpdateThreadMismatchLogged{false};',
    'std::atomic_bool g_hudUpdateThreadMismatchLogged{false};\nstd::atomic_bool g_hudMaskThreadMismatchLogged{false};',
    'mask thread diagnostic state',
)
native = replace_once(
    native,
    '    g_hudUpdateThreadMismatchLogged.store(false, std::memory_order_release);\n    g_nextHudSnapshotRefreshMs.store(0, std::memory_order_release);',
    '    g_hudUpdateThreadMismatchLogged.store(false, std::memory_order_release);\n    g_hudMaskThreadMismatchLogged.store(false, std::memory_order_release);\n    g_nextHudSnapshotRefreshMs.store(0, std::memory_order_release);',
    'snapshot reset state',
)

new_transaction_block = '''bool ShouldPinGameplayHudPresentation()
{
    if (!g_hudMaskTransactionAvailable.load(std::memory_order_acquire))
        return false;
    if (g_hudMaskPinSuspended.load(std::memory_order_acquire))
        return false;
    if (!g_gameplayHudSnapshot.captured)
        return false;
    if (g_cleanHidden.load(std::memory_order_acquire))
        return true;
    if (!g_pendingPauseAttempt.load(std::memory_order_acquire))
        return false;

    const ULONGLONG deadline = g_pendingDeadlineMs.load(std::memory_order_acquire);
    return deadline != 0 && GetTickCount64() <= deadline;
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

    for (std::size_t i = 0; i < kHudClipCount; ++i)
        target.visible[i] = visible[i];
    target.captured = true;
    return true;
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

    // Vanilla has already updated its internal C_UIHudMask state. Keep that state as
    // the source of truth and only roll the Flash presentation back before render.
    // The vanilla state is read live from I_UIHudMask when presentation is relinquished;
    // never snapshot all 28 Flash clips from a potentially partial source-event batch.
    if (!RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-mask-transaction"))
        Log("C_UIHudMask transaction could not restore gameplay HUD before render; periodic fallback remains active");
}

'''
native = replace_between(
    native,
    'bool ShouldPinGameplayHudPresentation()\n{',
    'void FailOpenHudMaintenance(const char* reason)\n{',
    new_transaction_block,
    'transaction block',
)

new_fail_open = '''void FailOpenHudMaintenance(const char* reason)
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

'''
native = replace_between(
    native,
    'void FailOpenHudMaintenance(const char* reason)\n{',
    'void __fastcall HookHudUpdate(void* element, float deltaTime)\n{',
    new_fail_open,
    'fail-open block',
)
native = replace_once(
    native,
    '    if (element != g_hudElement || !g_cleanHidden.load(std::memory_order_acquire))\n        return;',
    '    if (element != g_hudElement\n        || !g_cleanHidden.load(std::memory_order_acquire)\n        || g_hudMaskPinSuspended.load(std::memory_order_acquire))\n        return;',
    'HUD update suspension guard',
)
native = replace_once(
    native,
    '''    if (!hud_mask::EnsureHooks(hud, &ReconcileHudMaskMutation))
        Log("C_UIHudMask transaction hook unavailable; using snapshot restore fallback");
''',
    '''    bool maskAvailable = hud_mask::EnsureHooks(hud, &ReconcileHudMaskMutation);
    if (maskAvailable) {
        bool visibilityProbe[kHudClipCount]{};
        maskAvailable = hud_mask::ReadCurrentVisibility(
            hud, visibilityProbe, kHudClipCount);
    }
    g_hudMaskTransactionAvailable.store(maskAvailable, std::memory_order_release);
    if (!maskAvailable)
        Log("C_UIHudMask transaction unavailable; using snapshot restore fallback");
''',
    'mask availability probe',
)

new_clear_hidden = '''void ClearHiddenState(const char* reason)
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

'''
native = replace_between(
    native,
    'void ClearHiddenState(const char* reason)\n{',
    'void ArmPendingPauseAttempt()\n{',
    new_clear_hidden,
    'clear-hidden block',
)
new_pending = '''bool PendingAttemptAlive()
{
    if (!g_pendingPauseAttempt.load(std::memory_order_acquire))
        return false;
    if (GetTickCount64() <= g_pendingDeadlineMs.load(std::memory_order_acquire))
        return true;

    // A transactional mask callback may already have pinned gameplay presentation
    // before Menu@0 became verifiable. Expiry must restore KCD2's live internal state
    // rather than merely dropping the snapshot bookkeeping.
    g_hudMaskPinSuspended.store(true, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    if (g_gameplayHudSnapshot.captured
        && !RestoreVanillaHudPresentation("vanilla-pending-expiry"))
        Log("pending Clean Pause expiry could not restore current vanilla HUD presentation");
    ResetHudSnapshots();
    g_hudMaskPinSuspended.store(false, std::memory_order_release);
    return false;
}

'''
native = replace_between(
    native,
    'bool PendingAttemptAlive()\n{',
    'bool TryEnterCleanPause(const char* trigger, bool swallowMatchingRelease)\n{',
    new_pending,
    'pending block',
)
new_entry = '''bool TryEnterCleanPause(const char* trigger, bool swallowMatchingRelease)
{
    bool visible{};
    if (!ReadVerifiedMenuVisible(visible) || !visible)
        return false;
    if (!g_gameplayHudSnapshot.captured) {
        ResetHudSnapshots();
        Log("vanilla pause opened but gameplay HUD state was unavailable; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    const bool transactional =
        g_hudMaskTransactionAvailable.load(std::memory_order_acquire);
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
    g_swallowPauseRelease.store(swallowMatchingRelease, std::memory_order_release);
    g_pendingPauseAttempt.store(false, std::memory_order_release);
    g_pendingDeadlineMs.store(0, std::memory_order_release);
    Log("Running -> Clean Pause candidate: vanilla Menu@0 Render suppressed; DoF disabled (%s)",
        trigger ? trigger : "pause input");
    return true;
}

'''
native = replace_between(
    native,
    'bool TryEnterCleanPause(const char* trigger, bool swallowMatchingRelease)\n{',
    'void HandleHiddenInput(void* input, const InputEvent* event, bool force)\n{',
    new_entry,
    'entry block',
)
native = replace_once(
    native,
    '''        if (enteredAt != 0 && now - enteredAt > kRenderObservationGraceMs) {
            if (g_vanillaPauseHudSnapshot.captured)
                RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-fail-open");
            ClearHiddenState("Render suppression was not observed within 250 ms; fail-open");
''',
    '''        if (enteredAt != 0 && now - enteredAt > kRenderObservationGraceMs) {
            ClearHiddenState("Render suppression was not observed within 250 ms; fail-open");
''',
    'render fail-open dedupe',
)
native = replace_once(
    native,
    '            if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-visible-menu"))',
    '            if (!RestoreVanillaHudPresentation("vanilla-pause-visible-menu"))',
    'Start live vanilla restore',
)
native = replace_once(
    native,
    '        if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-visible-menu-via-B"))',
    '        if (!RestoreVanillaHudPresentation("vanilla-pause-visible-menu-via-B"))',
    'B live vanilla restore',
)
native = native.replace(
    'Log("Clean Pause -> visible vanilla pause menu via B (DoF restored; v0.1.0 behavior)");',
    'Log("Clean Pause -> visible vanilla pause menu via B (DoF restored; accepted behavior)");',
)
native = replace_once(
    native,
    '''    Log(
        "KCD2 Clean Pause v0.1.0 active; env=%p input=%p game(IGame*)=%p flashUI=%p mainThread=%lu PostInputEvent=%p",
        g_environment,
''',
    '''    Log(
        "KCD2 Clean Pause v%s build=%s active; env=%p input=%p game(IGame*)=%p flashUI=%p mainThread=%lu PostInputEvent=%p",
        CLEAN_PAUSE_VERSION,
        CLEAN_PAUSE_BUILD_ID,
        g_environment,
''',
    'active runtime identity log',
)
native = replace_once(
    native,
    '    Log("native bootstrap started; target=KCD2 1.5.6 Windows retail; KCD2 Clean Pause v0.1.0");',
    '    Log("native bootstrap started; target=KCD2 1.5.6 Windows retail; KCD2 Clean Pause v%s build=%s",\n        CLEAN_PAUSE_VERSION, CLEAN_PAUSE_BUILD_ID);',
    'bootstrap runtime identity log',
)
NATIVE_PATH.write_text(native, encoding="utf-8")

cmake = CMAKE_PATH.read_text(encoding="utf-8")
version_block = '''
file(READ "${CMAKE_CURRENT_SOURCE_DIR}/../VERSION" CLEAN_PAUSE_VERSION)
string(STRIP "${CLEAN_PAUSE_VERSION}" CLEAN_PAUSE_VERSION)
find_package(Git QUIET)
set(CLEAN_PAUSE_BUILD_ID "unknown")
if(GIT_FOUND)
  execute_process(
    COMMAND "${GIT_EXECUTABLE}" rev-parse --short=12 HEAD
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/.."
    OUTPUT_VARIABLE CLEAN_PAUSE_BUILD_ID
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
    RESULT_VARIABLE CLEAN_PAUSE_GIT_RESULT
  )
  if(NOT CLEAN_PAUSE_GIT_RESULT EQUAL 0 OR CLEAN_PAUSE_BUILD_ID STREQUAL "")
    set(CLEAN_PAUSE_BUILD_ID "unknown")
  endif()
endif()
'''
cmake = replace_once(
    cmake,
    'set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)\n',
    'set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)\n' + version_block,
    'CMake version identity block',
)
cmake = replace_once(
    cmake,
    '    _UNICODE\n  )',
    '    _UNICODE\n    CLEAN_PAUSE_VERSION="${CLEAN_PAUSE_VERSION}"\n    CLEAN_PAUSE_BUILD_ID="${CLEAN_PAUSE_BUILD_ID}"\n  )',
    'CMake compile identity definitions',
)
CMAKE_PATH.write_text(cmake, encoding="utf-8")

TEST_PATH.write_text(r'''import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
MASK = (ROOT / "native/src/clean_pause_hud_mask.cpp").read_text(encoding="utf-8")
MASK_H = (ROOT / "native/src/clean_pause_hud_mask.h").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class HudMaskTransactionContractTests(unittest.TestCase):
    def test_runtime_discovers_concrete_hud_mask_without_fixed_rva(self):
        self.assertIn('.?AVC_UIHudMask@guimodule@wh@@', MASK)
        self.assertIn('kMaskListenerOffset = 0x10', MASK)
        self.assertIn('kMaskVisibilityInterfaceOffset = 0x58', MASK)
        self.assertIn('kMaskSourceMonitorOffset = 0x60', MASK)
        self.assertIn('kHudListenersOffset = 0x1D0', MASK)
        self.assertNotIn('0x548BFA8', MASK)
        self.assertNotIn('0x180555978', MASK)

    def test_module_message_hook_filters_to_verified_refresh_message(self):
        self.assertIn('kModuleMessageIdOffset = 0x08', MASK)
        self.assertIn('kHudRefreshModuleMessageId = 52', MASK)
        hook = MASK[MASK.index('void __fastcall HookOnModuleMessage'):MASK.index('} // namespace\n\nbool EnsureHooks')]
        self.assertLess(hook.index('IsHudRefreshMessage(message)'), hook.index('g_originalOnModuleMessage'))
        self.assertIn('if (refresh)\n        NotifyAfterMutation();', hook)

    def test_vanilla_mutation_runs_before_visual_reconciliation(self):
        source = MASK[MASK.index('void __fastcall HookSourceEvent'):MASK.index('void __fastcall HookOnModuleMessage')]
        self.assertLess(source.index('g_originalSourceEvent'), source.index('NotifyAfterMutation'))
        module = MASK[MASK.index('void __fastcall HookOnModuleMessage'):MASK.index('} // namespace\n\nbool EnsureHooks')]
        self.assertLess(module.index('g_originalOnModuleMessage'), module.index('NotifyAfterMutation'))

    def test_live_vanilla_state_comes_from_internal_mask_interface(self):
        self.assertIn('kMaskIsElementVisibleSlot = 1', MASK)
        self.assertIn('ReadCurrentVisibility', MASK_H)
        read = MASK[MASK.index('bool ReadCurrentVisibility'):]
        self.assertIn('kMaskVisibilityInterfaceOffset', read)
        self.assertIn('VFunc<IsElementVisibleFn>', read)
        self.assertIn('count != kHudElementCount', read)

    def test_transaction_never_whole_snapshots_partial_flash_state(self):
        callback = NATIVE[NATIVE.index('void ReconcileHudMaskMutation()'):NATIVE.index('void FailOpenHudMaintenance')]
        self.assertNotIn('CaptureHudVisibilitySnapshot', callback)
        self.assertNotIn('g_vanillaPauseHudSnapshot =', callback)
        self.assertIn('RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot', callback)
        self.assertLess(callback.index('GetCurrentThreadId()'), callback.index('ShouldPinGameplayHudPresentation()'))

    def test_transaction_mode_does_not_require_fallback_vanilla_snapshot(self):
        entry = NATIVE[NATIVE.index('bool TryEnterCleanPause'):NATIVE.index('void HandleHiddenInput')]
        self.assertIn('const bool transactional', entry)
        self.assertIn('if (!transactional', entry)
        self.assertIn('CaptureHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause")', entry)

    def test_clean_pause_exit_suspends_all_pinning_before_live_restore(self):
        hidden = NATIVE[NATIVE.index('void HandleHiddenInput'):NATIVE.index('void __fastcall HookPostInputEvent')]
        start = hidden[hidden.index('if (IsPauseKey(key))'):hidden.index('if (key == KeyId::XiB)')]
        self.assertLess(start.index('g_hudMaskPinSuspended.store(true'), start.index('RestoreVanillaHudPresentation'))
        self.assertLess(start.index('RestoreVanillaHudPresentation'), start.index('g_cleanHidden.store(false'))
        self.assertLess(start.index('g_cleanHidden.store(false'), start.index('g_hudMaskPinSuspended.store(false'))

        b_path = hidden[hidden.index('if (key == KeyId::XiB)'):]
        self.assertLess(b_path.index('g_hudMaskPinSuspended.store(true'), b_path.index('RestoreVanillaHudPresentation'))
        self.assertLess(b_path.index('RestoreVanillaHudPresentation'), b_path.index('g_cleanHidden.store(false'))
        self.assertLess(b_path.index('g_cleanHidden.store(false'), b_path.index('g_hudMaskPinSuspended.store(false'))

    def test_periodic_fallback_respects_exit_suspension(self):
        update = NATIVE[NATIVE.index('void __fastcall HookHudUpdate'):NATIVE.index('bool EnsureHudUpdateHook')]
        self.assertIn('g_hudMaskPinSuspended.load(std::memory_order_acquire)', update)

    def test_pending_expiry_restores_live_vanilla_state_before_reset(self):
        pending = NATIVE[NATIVE.index('bool PendingAttemptAlive'):NATIVE.index('bool TryEnterCleanPause')]
        self.assertLess(pending.index('g_hudMaskPinSuspended.store(true'), pending.index('RestoreVanillaHudPresentation'))
        self.assertLess(pending.index('RestoreVanillaHudPresentation'), pending.index('ResetHudSnapshots'))

    def test_no_waiting_mechanism_is_added_to_transaction(self):
        callback = NATIVE[NATIVE.index('void ReconcileHudMaskMutation()'):NATIVE.index('void FailOpenHudMaintenance')]
        self.assertNotIn('Sleep(', callback)
        self.assertNotIn('while (', callback)
        self.assertNotIn('CreateThread', callback)

    def test_mask_hook_is_part_of_both_native_editions(self):
        self.assertIn('src/clean_pause_hud_mask.cpp', CMAKE)
        self.assertIn('src/clean_pause_hud_mask.h', CMAKE)
        self.assertIn('hud_mask::EnsureHooks(hud, &ReconcileHudMaskMutation)', NATIVE)


if __name__ == '__main__':
    unittest.main()
''', encoding="utf-8")

IDENTITY_TEST_PATH.write_text(r'''import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
CMAKE = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")


class RuntimeIdentityContractTests(unittest.TestCase):
    def test_runtime_identity_is_derived_from_version_and_git_head(self):
        self.assertIn('../VERSION', CMAKE)
        self.assertIn('rev-parse --short=12 HEAD', CMAKE)
        self.assertIn('CLEAN_PAUSE_VERSION="${CLEAN_PAUSE_VERSION}"', CMAKE)
        self.assertIn('CLEAN_PAUSE_BUILD_ID="${CLEAN_PAUSE_BUILD_ID}"', CMAKE)
        self.assertIn('CLEAN_PAUSE_VERSION', NATIVE)
        self.assertIn('CLEAN_PAUSE_BUILD_ID', NATIVE)
        self.assertNotIn('KCD2 Clean Pause v0.1.0 active', NATIVE)
        self.assertNotIn('KCD2 Clean Pause v0.1.0")', NATIVE)


if __name__ == '__main__':
    unittest.main()
''', encoding="utf-8")
