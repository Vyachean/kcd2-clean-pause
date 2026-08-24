from pathlib import Path
import subprocess
import sys
import tempfile

if len(sys.argv) != 3:
    raise SystemExit("usage: generate_candidate_v5.py <input.cpp> <output.cpp>")

source_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
v4 = Path(__file__).with_name("generate_candidate_v4.py")

with tempfile.TemporaryDirectory() as tmp:
    intermediate = Path(tmp) / "rc7e.cpp"
    subprocess.run([sys.executable, str(v4), str(source_path), str(intermediate)], check=True)
    source = intermediate.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"rc7f {label}: expected one match, got {count}")
    source = source.replace(old, new, 1)


# RC7e proved that the 28-child HUD snapshot restores subtitles, but its implementation
# retained IFlashVariableObject wrappers across frames and released them from an input
# transition while Menu::Render could still be using the same wrappers. RC7f keeps only
# bool state. Every GetMovieClip wrapper is acquired/used/released in one main-thread call.
old_state = r'''constexpr ULONGLONG kHudSnapshotHoldMs = 750;
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

struct HudClipSnapshot {
    void* clip{};
    bool visible{};
};

HudClipSnapshot g_hudClipSnapshot[kHudClipCount]{};
std::atomic_bool g_hudSnapshotCaptured{false};
std::atomic_bool g_hudSnapshotRestoreObserved{false};'''
new_state = r'''constexpr ULONGLONG kHudSnapshotHoldMs = 750;
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
void* g_hudUpdateTarget{};'''
replace_once(old_state, new_state, "replace retained-wrapper snapshot state")

# Replace the whole RC7e wrapper-owning helper block. No engine-owned Flash wrapper may
# survive past one helper call in RC7f.
helpers_start = source.find("void ReleaseHudClipSnapshot()\n{")
helpers_end = source.find("void __fastcall HookMenuRender(void* element)\n{", helpers_start)
if helpers_start == -1 or helpers_end == -1:
    raise SystemExit("rc7f could not locate rc7e HUD snapshot helper block")

new_helpers = r'''void ResetHudSnapshots()
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

bool ReleaseFlashVariable(void* clip)
{
    if (!clip || !ValidateObjectVtable(clip, {kFlashVariableReleaseSlot}))
        return false;
    const auto release = VFunc<FlashVariableReleaseFn>(clip, kFlashVariableReleaseSlot);
    if (!release || !IsExecutable(reinterpret_cast<void*>(release)))
        return false;
    __try {
        release(clip);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
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
                kFlashVariableReleaseSlot,
                kFlashVariableGetDisplayInfoSlot,
                kFlashVariableSetVisibleSlot })) {
            if (clip)
                ReleaseFlashVariable(clip);
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
        if (!ReleaseFlashVariable(clip))
            ok = false;
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
                kFlashVariableReleaseSlot,
                kFlashVariableSetVisibleSlot })) {
            if (clip)
                ReleaseFlashVariable(clip);
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
        if (!ReleaseFlashVariable(clip))
            ok = false;
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
    // ordinary vanilla pause. Best-effort restore the vanilla-pause child snapshot first.
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
    if (g_originalHudUpdate)
        g_originalHudUpdate(element, deltaTime);

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

'''
source = source[:helpers_start] + new_helpers + source[helpers_end:]

# Menu::Render is presentation-only again. It must never touch or free Flash wrappers.
render_start = source.find("void __fastcall HookMenuRender(void* element)\n{")
render_end = source.find("bool EnsureMenuRenderHook()", render_start)
if render_start == -1 or render_end == -1:
    raise SystemExit("rc7f could not locate rc7e Menu render hook")
source = source[:render_start] + r'''void __fastcall HookMenuRender(void* element)
{
    if (g_cleanHidden.load(std::memory_order_acquire) && element == g_menuElement) {
        if (!g_renderSuppressionObserved.exchange(true, std::memory_order_acq_rel))
            Log("Clean Pause render suppression observed for Menu@0");
        return;
    }

    if (g_originalRender)
        g_originalRender(element);
}

''' + source[render_end:]

# Pre-pause capture now stores bools only and also establishes the main-thread HUD Update
# hook that performs bounded late-refresh maintenance.
replace_once(
    "        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook() || !CaptureHudClipSnapshot()) {",
    r'''        ResetHudSnapshots();
        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook() || !EnsureHudUpdateHook()
            || !CaptureHudVisibilitySnapshot(g_gameplayHudSnapshot, "gameplay-pre-pause")) {''',
    "replace pre-pause retained-wrapper capture",
)

# All old wrapper-release calls become state-only resets. Engine wrappers are now already
# released before each helper returns.
source = source.replace("ReleaseHudClipSnapshot();", "ResetHudSnapshots();")
if "ReleaseHudClipSnapshot" in source or "g_hudClipSnapshot" in source or "g_hudSnapshotCaptured" in source:
    raise SystemExit("rc7f retained an rc7e long-lived wrapper symbol")

# Capture the true vanilla-pause child state before overriding it. This gives second
# Start/fail-open/B a safe exact state to restore instead of guessing which clips hide.
old_enter = r'''    if (!g_hudSnapshotCaptured.load(std::memory_order_acquire) || !RestoreHudClipSnapshot()) {
        ResetHudSnapshots();
        Log("vanilla pause opened but HUD child snapshot could not be restored; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(GetTickCount64(), std::memory_order_release);
    g_cleanHidden.store(true, std::memory_order_release);'''
new_enter = r'''    if (!g_gameplayHudSnapshot.captured
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

    const ULONGLONG enteredAt = GetTickCount64();
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(enteredAt, std::memory_order_release);
    g_nextHudSnapshotRefreshMs.store(enteredAt + kHudSnapshotRefreshIntervalMs, std::memory_order_release);
    g_cleanHidden.store(true, std::memory_order_release);'''
replace_once(old_enter, new_enter, "capture vanilla-pause snapshot before gameplay restore")

# A render-observation timeout means Menu is still logically open. Restore the captured
# vanilla-pause child state before failing open to visible Menu.
replace_once(
    '            ClearHiddenState("Render suppression was not observed within 250 ms; fail-open");',
    r'''            if (g_vanillaPauseHudSnapshot.captured)
                RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-fail-open");
            ClearHiddenState("Render suppression was not observed within 250 ms; fail-open");''',
    "restore pause HUD on render timeout",
)

# Second Start/Escape reveals the already-open vanilla menu. Restore the exact child
# state captured from vanilla pause before dropping Menu render suppression.
old_second_pause = r'''        if (pressed) {
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            ResetHudSnapshots();
            g_swallowPauseRelease.store(true, std::memory_order_release);
            Log("Clean Pause -> visible vanilla pause menu (second Escape/Start consumed; Render restored)");
            return;
        }'''
new_second_pause = r'''        if (pressed) {
            if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-visible-menu"))
                Log("could not restore captured vanilla-pause HUD before showing Menu; continuing fail-open");
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            ResetHudSnapshots();
            g_swallowPauseRelease.store(true, std::memory_order_release);
            Log("Clean Pause -> visible vanilla pause menu (second Escape/Start consumed; Render restored)");
            return;
        }'''
replace_once(old_second_pause, new_second_pause, "restore vanilla child state on second pause key")

# B must transition from the same exact vanilla-pause child state that would exist behind
# a visible Menu. If that restore cannot be proven, do not attempt the synthetic toggle.
old_b_prelude = r'''        if (!pressed)
            return;

        if (ReplayVanillaPauseToggle(input, force)) {'''
new_b_prelude = r'''        if (!pressed)
            return;

        if (!RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-before-B")) {
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            ResetHudSnapshots();
            g_swallowResumeRelease.store(true, std::memory_order_release);
            Log("B resume aborted: vanilla-pause HUD snapshot restore failed; showing ordinary pause menu (fail-open)");
            return;
        }

        if (ReplayVanillaPauseToggle(input, force)) {'''
replace_once(old_b_prelude, new_b_prelude, "restore vanilla child state before B replay")

# Update stale RC7e wording in generated runtime markers.
source = source.replace(
    "rc7e child-HUD-snapshot render-suppression candidate active; env=%p",
    "rc7f race-free child-HUD-snapshot candidate active; env=%p",
)
source = source.replace(
    "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7e child-HUD-snapshot render-suppression candidate",
    "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7f race-free child-HUD-snapshot candidate",
)
source = source.replace(
    "HUD child visibility snapshot captured for all 28 clips",
    "HUD visibility snapshot captured for all 28 clips",
)

required = (
    "HudVisibilitySnapshot g_gameplayHudSnapshot",
    "HudVisibilitySnapshot g_vanillaPauseHudSnapshot",
    "ReleaseFlashVariable",
    "CaptureHudVisibilitySnapshot",
    "RestoreHudVisibilitySnapshot",
    'CaptureHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause")',
    'RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-visible-menu")',
    'RestoreHudVisibilitySnapshot(g_vanillaPauseHudSnapshot, "vanilla-pause-before-B")',
    "EnsureHudUpdateHook",
    "HookHudUpdate",
    "kUIElementUpdateSlot",
    "GetCurrentThreadId() != g_mainThreadId",
    "kHudSnapshotRefreshIntervalMs = 75",
    "Clean Pause gameplay HUD snapshot restored across all 28 clips",
    "ReplayVanillaPauseToggle",
    "XiB",
    "rc7f race-free child-HUD-snapshot candidate active",
)
for needle in required:
    if needle not in source:
        raise SystemExit(f"generated rc7f source missing: {needle}")

for forbidden in (
    "HudClipSnapshot",
    "g_hudClipSnapshot",
    "ReleaseHudClipSnapshot",
    "g_hudSnapshotCaptured",
    "snapshot.clip",
    "RestoreHudClipSnapshot()",
    "SetHudGateVisible",
    "HookHudSetVisible",
    "HookGlobalHudVisibility",
):
    if forbidden in source:
        raise SystemExit(f"generated rc7f source retained unsafe/rejected path: {forbidden}")

# Cross-thread safety: Menu Render may suppress drawing only. It must never perform
# Flash child acquisition/mutation or wrapper release.
menu_hook = source[source.index("void __fastcall HookMenuRender"):source.index("bool EnsureMenuRenderHook")]
for forbidden in (
    "GetMovieClip",
    "RestoreHudVisibilitySnapshot",
    "ReleaseFlashVariable",
    "ResetHudSnapshots",
    "SetVisible",
):
    if forbidden in menu_hook:
        raise SystemExit(f"Menu Render hook performs forbidden HUD lifecycle work: {forbidden}")

# Every capture/restore loop must release its fresh wrapper before leaving that iteration.
capture = source[source.index("bool CaptureHudVisibilitySnapshot"):source.index("bool RestoreHudVisibilitySnapshot")]
restore = source[source.index("bool RestoreHudVisibilitySnapshot"):source.index("void FailOpenHudMaintenance")]
if capture.count("ReleaseFlashVariable(clip)") < 3:
    raise SystemExit("capture path does not visibly release fresh wrappers on all outcomes")
if restore.count("ReleaseFlashVariable(clip)") < 3:
    raise SystemExit("restore path does not visibly release fresh wrappers on all outcomes")

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(source, encoding="utf-8")
print(f"generated rc7f source: {out_path}")
