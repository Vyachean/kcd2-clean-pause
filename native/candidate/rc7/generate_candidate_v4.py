from pathlib import Path
import re
import subprocess
import sys
import tempfile

if len(sys.argv) != 3:
    raise SystemExit("usage: generate_candidate_v4.py <input.cpp> <output.cpp>")

source_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
v2 = Path(__file__).with_name("generate_candidate_v2.py")

with tempfile.TemporaryDirectory() as tmp:
    intermediate = Path(tmp) / "rc7c.cpp"
    subprocess.run([sys.executable, str(v2), str(source_path), str(intermediate)], check=True)
    source = intermediate.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global source
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"rc7e {label}: expected one match, got {count}")
    source = source.replace(old, new, 1)


# rc7c's one-shot/global HUD-gate experiment is deliberately removed. Retail rc7d
# proved that whole-element visibility is not the presentation layer hiding KCD2's HUD.
replace_once(
    "using SetHudElementsVisibleFn = void(__fastcall*)(void*, bool);\n",
    "",
    "remove global HUD typedef",
)
replace_once(
    "constexpr std::size_t kFlashUISetHudElementsVisibleSlot = 28;\n",
    "",
    "remove global HUD slot",
)
replace_once(
    "std::atomic_bool g_hudGateForcedVisible{false};\n",
    "",
    "remove global HUD state",
)
replace_once(
    "    if (!ValidateObjectVtable(value.flashUI, {\n            kFlashUIGetElementByInstanceStrSlot,\n            kFlashUISetHudElementsVisibleSlot }))\n        return false;",
    "    if (!ValidateObjectVtable(value.flashUI, {kFlashUIGetElementByInstanceStrSlot}))\n        return false;",
    "restore FlashUI validation",
)

start = source.find("bool SetHudGateVisible(bool visible)\n{")
end = source.find("bool ShouldFreezeHudFunction", start)
if start == -1 or end == -1:
    raise SystemExit("rc7e could not remove rc7c SetHudGateVisible helper")
source = source[:start] + source[end:]

# Remove every active rc7c HUD-gate call/state transition. Do this before adding the
# child-clip snapshot implementation, then assert that no old mechanism survives.
source = re.sub(
    r"\n\s*if \(g_hudGateForcedVisible\.exchange\(false, std::memory_order_acq_rel\)\)\n\s*SetHudGateVisible\(false\);",
    "",
    source,
)
source = re.sub(
    r"\n\s*if \(g_hudGateForcedVisible\.exchange\(false, std::memory_order_acq_rel\)\n\s*&& !SetHudGateVisible\(false\)\)\n\s*Log\([^\n]*\);",
    "",
    source,
)
source = re.sub(
    r"\n\s*g_hudGateForcedVisible\.store\((?:true|false), std::memory_order_release\);",
    "",
    source,
)
source = re.sub(
    r'''\n\s*if \(!SetHudGateVisible\(true\)\) \{\n\s*Log\("vanilla pause opened but HUD visibility gate could not be restored; leaving ordinary visible pause menu \(fail-open\)"\);\n\s*return false;\n\s*\}''',
    "",
    source,
)
if "SetHudGateVisible" in source or "g_hudGateForcedVisible" in source:
    raise SystemExit("rc7e generated source still contains rejected root-HUD gate path")

# Snapshot state is stored as engine-owned IFlashVariableObject wrappers. The wrappers
# are acquired before vanilla pause changes C_UIHudMask's 28 child movie clips and are
# released whenever Clean Pause ownership ends.
replace_once(
    "void* g_hudCallFunctionTarget{};",
    r'''void* g_hudCallFunctionTarget{};

constexpr ULONGLONG kHudSnapshotHoldMs = 750;
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
std::atomic_bool g_hudSnapshotRestoreObserved{false};''',
    "add child HUD snapshot state",
)

marker = "void __fastcall HookMenuRender(void* element)\n{"
functions = r'''void ReleaseHudClipSnapshot()
{
    g_hudSnapshotCaptured.store(false, std::memory_order_release);
    g_hudSnapshotRestoreObserved.store(false, std::memory_order_release);

    for (auto& snapshot : g_hudClipSnapshot) {
        if (!snapshot.clip)
            continue;
        const auto release = VFunc<FlashVariableReleaseFn>(
            snapshot.clip, kFlashVariableReleaseSlot);
        if (release && IsExecutable(reinterpret_cast<void*>(release))) {
            __try {
                release(snapshot.clip);
            } __except (EXCEPTION_EXECUTE_HANDLER) {
            }
        }
        snapshot = {};
    }
}

bool CaptureHudClipSnapshot()
{
    ReleaseHudClipSnapshot();

    void* hud{};
    if (!ResolveHudElement(hud))
        return false;
    if (!ValidateObjectVtable(hud, {kUIElementGetMovieClipByNameSlot}))
        return false;

    const auto getMovieClip = VFunc<GetMovieClipByNameFn>(
        hud, kUIElementGetMovieClipByNameSlot);
    if (!getMovieClip || !IsExecutable(reinterpret_cast<void*>(getMovieClip)))
        return false;

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
            if (clip) {
                const auto release = VFunc<FlashVariableReleaseFn>(clip, kFlashVariableReleaseSlot);
                if (release) {
                    __try { release(clip); } __except (EXCEPTION_EXECUTE_HANDLER) {}
                }
            }
            Log("HUD clip snapshot unavailable at %s; leaving vanilla behavior untouched", kHudClipNames[i]);
            ReleaseHudClipSnapshot();
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
            const auto release = VFunc<FlashVariableReleaseFn>(clip, kFlashVariableReleaseSlot);
            if (release) {
                __try { release(clip); } __except (EXCEPTION_EXECUTE_HANDLER) {}
            }
            Log("HUD clip display state unavailable at %s; leaving vanilla behavior untouched", kHudClipNames[i]);
            ReleaseHudClipSnapshot();
            return false;
        }

        g_hudClipSnapshot[i].clip = clip;
        g_hudClipSnapshot[i].visible = info[kFlashDisplayInfoVisibleOffset] != 0;
    }

    g_hudSnapshotCaptured.store(true, std::memory_order_release);
    Log("HUD child visibility snapshot captured for all 28 clips");
    return true;
}

bool RestoreHudClipSnapshot()
{
    if (!g_hudSnapshotCaptured.load(std::memory_order_acquire))
        return false;

    // C_UIHudMask controls child clips, not hud@0 itself, but keeping the already
    // resolved root visible is a necessary container invariant while restoring them.
    void* hud{};
    if (!ResolveHudElement(hud) || hud != g_hudElement)
        return false;
    const auto setRootVisible = VFunc<SetVisibleFn>(hud, kUIElementSetVisibleSlot);
    if (!setRootVisible || !IsExecutable(reinterpret_cast<void*>(setRootVisible)))
        return false;

    __try {
        setRootVisible(hud, true);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }

    for (const auto& snapshot : g_hudClipSnapshot) {
        if (!snapshot.clip)
            return false;
        const auto setVisible = VFunc<FlashVariableSetVisibleFn>(
            snapshot.clip, kFlashVariableSetVisibleSlot);
        if (!setVisible || !IsExecutable(reinterpret_cast<void*>(setVisible)))
            return false;
        bool ok{};
        __try {
            ok = setVisible(snapshot.clip, snapshot.visible);
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            ok = false;
        }
        if (!ok)
            return false;
    }

    if (!g_hudSnapshotRestoreObserved.exchange(true, std::memory_order_acq_rel))
        Log("Clean Pause HUD child snapshot restored across all 28 clips");
    return true;
}

void __fastcall HookMenuRender(void* element)
{'''
replace_once(marker, functions, "insert HUD snapshot helpers")

old_render = r'''    if (g_cleanHidden.load(std::memory_order_acquire) && element == g_menuElement) {
        if (!g_renderSuppressionObserved.exchange(true, std::memory_order_acq_rel))
            Log("Clean Pause render suppression observed for Menu@0");
        return;
    }'''
new_render = r'''    if (g_cleanHidden.load(std::memory_order_acquire) && element == g_menuElement) {
        const ULONGLONG enteredAt = g_cleanHiddenSinceMs.load(std::memory_order_acquire);
        if (enteredAt != 0 && GetTickCount64() - enteredAt <= kHudSnapshotHoldMs) {
            if (!RestoreHudClipSnapshot()) {
                g_cleanHidden.store(false, std::memory_order_release);
                g_renderSuppressionObserved.store(false, std::memory_order_release);
                ReleaseHudClipSnapshot();
                Log("HUD child snapshot restore failed; showing ordinary vanilla pause menu (fail-open)");
                if (g_originalRender)
                    g_originalRender(element);
                return;
            }
        }
        if (!g_renderSuppressionObserved.exchange(true, std::memory_order_acq_rel))
            Log("Clean Pause render suppression observed for Menu@0");
        return;
    }'''
replace_once(old_render, new_render, "extend Menu render hook")

# Always release engine-owned child wrappers when hidden-pause ownership is cleared.
replace_once(
    "    g_pendingDeadlineMs.store(0, std::memory_order_release);\n    if (reason)",
    "    g_pendingDeadlineMs.store(0, std::memory_order_release);\n    ReleaseHudClipSnapshot();\n    if (reason)",
    "release snapshot from ClearHiddenState",
)

# A valid snapshot must be captured before KCD2 receives the physical pause press.
replace_once(
    "        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook()) {",
    "        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook() || !CaptureHudClipSnapshot()) {",
    "require pre-pause HUD snapshot",
)
replace_once(
    "            Log(\"pause input: required Menu/HUD presentation hooks unavailable; leaving vanilla behavior untouched\");",
    "            ReleaseHudClipSnapshot();\n            Log(\"pause input: Menu/HUD snapshot path unavailable; leaving vanilla behavior untouched\");",
    "update fail-open log",
)

# If this wasn't a Running -> pause transition after all, don't retain the wrappers.
replace_once(
    "        if (!ReadVerifiedMenuVisible(visibleBefore) || visibleBefore) {\n            g_pendingPauseAttempt.store(false, std::memory_order_release);\n            Forward(input, event, force);",
    "        if (!ReadVerifiedMenuVisible(visibleBefore) || visibleBefore) {\n            g_pendingPauseAttempt.store(false, std::memory_order_release);\n            ReleaseHudClipSnapshot();\n            Forward(input, event, force);",
    "release snapshot for already-visible Menu",
)

# Once vanilla pause is verified, the captured child state becomes the presentation
# invariant. Reapply immediately, then the Menu render hook keeps it pinned briefly
# across any late UI-source refreshes during transition.
replace_once(
    "    g_renderSuppressionObserved.store(false, std::memory_order_release);\n    g_cleanHiddenSinceMs.store(GetTickCount64(), std::memory_order_release);\n    g_cleanHidden.store(true, std::memory_order_release);",
    r'''    if (!g_hudSnapshotCaptured.load(std::memory_order_acquire) || !RestoreHudClipSnapshot()) {
        ReleaseHudClipSnapshot();
        Log("vanilla pause opened but HUD child snapshot could not be restored; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(GetTickCount64(), std::memory_order_release);
    g_cleanHidden.store(true, std::memory_order_release);''',
    "restore snapshot on Clean Pause entry",
)

# Explicit state exits in rc7c do not all call ClearHiddenState.
replace_once(
    "            g_swallowPauseRelease.store(true, std::memory_order_release);\n            Log(\"Clean Pause -> visible vanilla pause menu",
    "            ReleaseHudClipSnapshot();\n            g_swallowPauseRelease.store(true, std::memory_order_release);\n            Log(\"Clean Pause -> visible vanilla pause menu",
    "release snapshot on second pause key",
)
replace_once(
    "            g_swallowResumeRelease.store(true, std::memory_order_release);\n            Log(\"Clean Pause -> running via B using replayed vanilla pause toggle\");",
    "            ReleaseHudClipSnapshot();\n            g_swallowResumeRelease.store(true, std::memory_order_release);\n            Log(\"Clean Pause -> running via B using replayed vanilla pause toggle\");",
    "release snapshot on B resume",
)

# Give pending acquisition expiry a cleanup path too.
replace_once(
    "    g_pendingPauseAttempt.store(false, std::memory_order_release);\n    g_pendingDeadlineMs.store(0, std::memory_order_release);\n    return false;\n}\n\nbool TryEnterCleanPause",
    "    g_pendingPauseAttempt.store(false, std::memory_order_release);\n    g_pendingDeadlineMs.store(0, std::memory_order_release);\n    ReleaseHudClipSnapshot();\n    return false;\n}\n\nbool TryEnterCleanPause",
    "release expired pending snapshot",
)

source = source.replace(
    "rc7c HUD-preserving render-suppression candidate active; env=%p",
    "rc7e child-HUD-snapshot render-suppression candidate active; env=%p",
)
source = source.replace(
    "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7c HUD-preserving render-suppression candidate",
    "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7e child-HUD-snapshot render-suppression candidate",
)

required = (
    "kHudClipCount = 28",
    '"Subtitles"',
    '"Hints"',
    "kUIElementGetMovieClipByNameSlot",
    "kFlashVariableGetDisplayInfoSlot",
    "kFlashVariableSetVisibleSlot",
    "CaptureHudClipSnapshot",
    "HUD child visibility snapshot captured for all 28 clips",
    "Clean Pause HUD child snapshot restored across all 28 clips",
    "kHudSnapshotHoldMs = 750",
    "ReplayVanillaPauseToggle",
    "ClearSubtitles",
    "HideNarrativeSubtitles",
    "rc7e child-HUD-snapshot render-suppression candidate active",
)
for needle in required:
    if needle not in source:
        raise SystemExit(f"generated rc7e source missing: {needle}")

for forbidden in (
    "SetHudGateVisible",
    "g_hudGateForcedVisible",
    "HookHudSetVisible",
    "HookGlobalHudVisible",
    "kHudElementSetVisibleSlot",
):
    if forbidden in source:
        raise SystemExit(f"generated rc7e source retained rejected visibility path: {forbidden}")

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(source, encoding="utf-8")
print(f"generated rc7e source: {out_path}")
