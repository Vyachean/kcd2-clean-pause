from pathlib import Path
import subprocess
import sys
import tempfile

if len(sys.argv) != 3:
    raise SystemExit("usage: generate_candidate_v3.py <input.cpp> <output.cpp>")

source_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
v2 = Path(__file__).with_name("generate_candidate_v2.py")

with tempfile.TemporaryDirectory() as tmp:
    intermediate = Path(tmp) / "rc7c.cpp"
    subprocess.run([sys.executable, str(v2), str(source_path), str(intermediate)], check=True)
    source = intermediate.read_text(encoding="utf-8")

replacements = [
    (
        "using SetHudElementsVisibleFn = void(__fastcall*)(void*, bool);\nusing HudCallFunctionFn = bool(__fastcall*)(void*, const char*, const void*, void*, const char*);\nRenderFn g_originalRender{};\nvoid* g_renderTarget{};\nvoid* g_hudElement{};\nHudCallFunctionFn g_originalHudCallFunction{};\nvoid* g_hudCallFunctionTarget{};",
        "using SetHudElementsVisibleFn = void(__fastcall*)(void*, bool);\nusing HudCallFunctionFn = bool(__fastcall*)(void*, const char*, const void*, void*, const char*);\nusing HudSetVisibleFn = void(__fastcall*)(void*, bool);\nusing HudIsVisibleFn = bool(__fastcall*)(void*);\nRenderFn g_originalRender{};\nvoid* g_renderTarget{};\nvoid* g_hudElement{};\nHudCallFunctionFn g_originalHudCallFunction{};\nvoid* g_hudCallFunctionTarget{};\nHudSetVisibleFn g_originalHudSetVisible{};\nvoid* g_hudSetVisibleTarget{};\nstd::atomic_bool g_hudHideSuppressionObserved{false};",
    ),
    (
        "constexpr std::size_t kFlashUISetHudElementsVisibleSlot = 28;\nconstexpr std::size_t kUIElementCallFunctionByNameSlot = 69;",
        "constexpr std::size_t kFlashUISetHudElementsVisibleSlot = 28;\nconstexpr std::size_t kHudElementSetVisibleSlot = 28;\nconstexpr std::size_t kUIElementCallFunctionByNameSlot = 69;",
    ),
    (
        "    return hud && ValidateObjectVtable(hud, {kUIElementCallFunctionByNameSlot});",
        "    return hud && ValidateObjectVtable(hud, {\n        kUIElementCallFunctionByNameSlot,\n        kHudElementSetVisibleSlot,\n        kUIElementIsVisibleSlot });",
    ),
    (
        "    g_hudGateForcedVisible.store(false, std::memory_order_release);\n    g_swallowPauseRelease.store(false, std::memory_order_release);",
        "    g_hudGateForcedVisible.store(false, std::memory_order_release);\n    g_hudHideSuppressionObserved.store(false, std::memory_order_release);\n    g_swallowPauseRelease.store(false, std::memory_order_release);",
    ),
    (
        "        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook()) {",
        "        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook() || !EnsureHudVisibilityHook()) {",
    ),
    (
        "rc7c HUD-preserving render-suppression candidate active; env=%p",
        "rc7d concrete-HUD render-suppression candidate active; env=%p",
    ),
    (
        "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7c HUD-preserving render-suppression candidate",
        "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7d concrete-HUD render-suppression candidate",
    ),
]

for old, new in replacements:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"rc7d expected exactly one source match, got {count}: {old[:120]!r}")
    source = source.replace(old, new, 1)

marker = "    return true;\n}\n\nvoid __fastcall HookMenuRender(void* element)"
addition = r'''    return true;
}

bool ShouldHoldConcreteHudVisible()
{
    if (g_cleanHidden.load(std::memory_order_acquire))
        return true;
    if (!g_pendingPauseAttempt.load(std::memory_order_acquire))
        return false;
    const ULONGLONG deadline = g_pendingDeadlineMs.load(std::memory_order_acquire);
    return deadline != 0 && GetTickCount64() <= deadline;
}

void __fastcall HookHudSetVisible(void* element, bool visible)
{
    if (element == g_hudElement && !visible && ShouldHoldConcreteHudVisible()) {
        if (!g_hudHideSuppressionObserved.exchange(true, std::memory_order_acq_rel))
            Log("Clean Pause HUD preservation: suppressed hud@0 SetVisible(false)");
        return;
    }

    if (g_originalHudSetVisible)
        g_originalHudSetVisible(element, visible);
}

bool EnsureHudVisibilityHook()
{
    void* hud{};
    if (!ResolveHudElement(hud))
        return false;

    const auto target = reinterpret_cast<void*>(
        VFunc<HudSetVisibleFn>(hud, kHudElementSetVisibleSlot));
    if (!target || !IsExecutable(target))
        return false;

    if (g_hudSetVisibleTarget) {
        if (target != g_hudSetVisibleTarget)
            return false;
        g_hudElement = hud;
        return true;
    }

    g_hudElement = hud;
    const MH_STATUS create = MH_CreateHook(
        target,
        reinterpret_cast<void*>(&HookHudSetVisible),
        reinterpret_cast<void**>(&g_originalHudSetVisible));
    if (create != MH_OK) {
        Log("MH_CreateHook(HUD SetVisible) failed: %d", static_cast<int>(create));
        return false;
    }

    const MH_STATUS enable = MH_EnableHook(target);
    if (enable != MH_OK) {
        Log("MH_EnableHook(HUD SetVisible) failed: %d", static_cast<int>(enable));
        return false;
    }

    g_hudSetVisibleTarget = target;
    Log("hud@0 concrete visibility hook active; hud=%p SetVisible=%p",
        g_hudElement,
        g_hudSetVisibleTarget);
    return true;
}

bool SetConcreteHudVisibleAndVerify(bool visible, bool bypassHold)
{
    void* hud{};
    if (!ResolveHudElement(hud) || hud != g_hudElement || !g_hudSetVisibleTarget)
        return false;

    const auto currentTarget = reinterpret_cast<void*>(
        VFunc<HudSetVisibleFn>(hud, kHudElementSetVisibleSlot));
    if (currentTarget != g_hudSetVisibleTarget)
        return false;

    const auto isVisible = VFunc<HudIsVisibleFn>(hud, kUIElementIsVisibleSlot);
    if (!isVisible)
        return false;

    __try {
        if (bypassHold) {
            if (!g_originalHudSetVisible)
                return false;
            g_originalHudSetVisible(hud, visible);
        } else {
            const auto setVisible = VFunc<HudSetVisibleFn>(hud, kHudElementSetVisibleSlot);
            if (!setVisible)
                return false;
            setVisible(hud, visible);
        }
        return isVisible(hud) == visible;
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
}

void RestoreVisibleVanillaPausePresentation()
{
    g_cleanHidden.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(0, std::memory_order_release);

    if (g_hudGateForcedVisible.exchange(false, std::memory_order_acq_rel)
        && !SetHudGateVisible(false))
        Log("could not restore vanilla global HUD-hidden pause presentation");

    if (!SetConcreteHudVisibleAndVerify(false, true))
        Log("could not verify vanilla hud@0 hidden presentation");
}

void __fastcall HookMenuRender(void* element)'''
count = source.count(marker)
if count != 1:
    raise SystemExit(f"rc7d HUD visibility insertion marker count={count}")
source = source.replace(marker, addition, 1)

old_enter = r'''    if (!SetHudGateVisible(true)) {
        Log("vanilla pause opened but HUD visibility gate could not be restored; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    g_hudGateForcedVisible.store(true, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(GetTickCount64(), std::memory_order_release);
    g_cleanHidden.store(true, std::memory_order_release);'''
new_enter = r'''    if (!SetHudGateVisible(true) || !SetConcreteHudVisibleAndVerify(true, false)) {
        g_pendingPauseAttempt.store(false, std::memory_order_release);
        g_pendingDeadlineMs.store(0, std::memory_order_release);
        g_cleanHidden.store(false, std::memory_order_release);
        SetHudGateVisible(false);
        SetConcreteHudVisibleAndVerify(false, true);
        Log("vanilla pause opened but concrete hud@0 visibility could not be restored; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    g_hudGateForcedVisible.store(true, std::memory_order_release);
    g_hudHideSuppressionObserved.store(false, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(GetTickCount64(), std::memory_order_release);
    g_cleanHidden.store(true, std::memory_order_release);
    Log("Clean Pause HUD presentation verified: hud@0 visible=true");'''
if source.count(old_enter) != 1:
    raise SystemExit("rc7d could not replace rc7c enter-HUD block")
source = source.replace(old_enter, new_enter, 1)

old_second = r'''        if (pressed) {
            if (g_hudGateForcedVisible.exchange(false, std::memory_order_acq_rel)
                && !SetHudGateVisible(false))
                Log("could not restore vanilla HUD-hidden pause presentation before showing Menu");
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            g_swallowPauseRelease.store(true, std::memory_order_release);'''
new_second = r'''        if (pressed) {
            RestoreVisibleVanillaPausePresentation();
            g_swallowPauseRelease.store(true, std::memory_order_release);'''
if source.count(old_second) != 1:
    raise SystemExit("rc7d could not replace second-pause presentation block")
source = source.replace(old_second, new_second, 1)

old_verify_fail = r'''    if (!ReadVerifiedMenuVisible(visible)) {
        if (g_hudGateForcedVisible.exchange(false, std::memory_order_acq_rel))
            SetHudGateVisible(false);
        ClearHiddenState("vanilla Menu@0 verification failed; ordinary pause presentation restored");
        Forward(input, event, force);
        return;
    }'''
new_verify_fail = r'''    if (!ReadVerifiedMenuVisible(visible)) {
        RestoreVisibleVanillaPausePresentation();
        ClearHiddenState("vanilla Menu@0 verification failed; ordinary pause presentation restored");
        Forward(input, event, force);
        return;
    }'''
if source.count(old_verify_fail) != 1:
    raise SystemExit("rc7d could not replace menu-verification fail-open block")
source = source.replace(old_verify_fail, new_verify_fail, 1)

old_render_fail = r'''        if (enteredAt != 0 && now - enteredAt > kRenderObservationGraceMs) {
            if (g_hudGateForcedVisible.exchange(false, std::memory_order_acq_rel))
                SetHudGateVisible(false);
            ClearHiddenState("Render suppression was not observed within 250 ms; fail-open");
            Forward(input, event, force);
            return;
        }'''
new_render_fail = r'''        if (enteredAt != 0 && now - enteredAt > kRenderObservationGraceMs) {
            RestoreVisibleVanillaPausePresentation();
            ClearHiddenState("Render suppression was not observed within 250 ms; fail-open");
            Forward(input, event, force);
            return;
        }'''
if source.count(old_render_fail) != 1:
    raise SystemExit("rc7d could not replace render fail-open block")
source = source.replace(old_render_fail, new_render_fail, 1)

old_b_fail = r'''        if (g_hudGateForcedVisible.exchange(false, std::memory_order_acq_rel))
            SetHudGateVisible(false);
        ClearHiddenState("B resume toggle was not verified; showing ordinary vanilla pause menu (fail-open)");
        g_swallowResumeRelease.store(true, std::memory_order_release);'''
new_b_fail = r'''        RestoreVisibleVanillaPausePresentation();
        ClearHiddenState("B resume toggle was not verified; showing ordinary vanilla pause menu (fail-open)");
        g_swallowResumeRelease.store(true, std::memory_order_release);'''
if source.count(old_b_fail) != 1:
    raise SystemExit("rc7d could not replace B fail-open block")
source = source.replace(old_b_fail, new_b_fail, 1)

required = (
    "rc7d concrete-HUD render-suppression candidate active",
    "kHudElementSetVisibleSlot = 28",
    "HookHudSetVisible",
    "element == g_hudElement && !visible && ShouldHoldConcreteHudVisible()",
    "suppressed hud@0 SetVisible(false)",
    "SetConcreteHudVisibleAndVerify(true, false)",
    "Clean Pause HUD presentation verified: hud@0 visible=true",
    "RestoreVisibleVanillaPausePresentation",
    "ReplayVanillaPauseToggle",
    "ClearSubtitles",
    "HideNarrativeSubtitles",
)
for needle in required:
    if needle not in source:
        raise SystemExit(f"generated rc7d source missing: {needle}")

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(source, encoding="utf-8")
print(f"generated rc7d source: {out_path}")
