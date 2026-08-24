from pathlib import Path
import subprocess
import sys
import tempfile

if len(sys.argv) != 3:
    raise SystemExit("usage: generate_candidate_v3.py <input.cpp> <output.cpp>")

source_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
base = Path(__file__).with_name("generate_candidate_v3_base.py")

with tempfile.TemporaryDirectory() as tmp:
    intermediate = Path(tmp) / "rc7d-concrete-hud.cpp"
    subprocess.run([sys.executable, str(base), str(source_path), str(intermediate)], check=True)
    source = intermediate.read_text(encoding="utf-8")

replacements = [
    (
        "HudSetVisibleFn g_originalHudSetVisible{};\nvoid* g_hudSetVisibleTarget{};\nstd::atomic_bool g_hudHideSuppressionObserved{false};",
        "HudSetVisibleFn g_originalHudSetVisible{};\nvoid* g_hudSetVisibleTarget{};\nSetHudElementsVisibleFn g_originalSetHudElementsVisible{};\nvoid* g_setHudElementsVisibleTarget{};\nstd::atomic_bool g_hudHideSuppressionObserved{false};\nstd::atomic_bool g_globalHudHideSuppressionObserved{false};",
    ),
    (
        "    g_hudHideSuppressionObserved.store(false, std::memory_order_release);\n    g_swallowPauseRelease.store(false, std::memory_order_release);",
        "    g_hudHideSuppressionObserved.store(false, std::memory_order_release);\n    g_globalHudHideSuppressionObserved.store(false, std::memory_order_release);\n    g_swallowPauseRelease.store(false, std::memory_order_release);",
    ),
    (
        "        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook() || !EnsureHudVisibilityHook()) {",
        "        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook() || !EnsureHudVisibilityHook() || !EnsureGlobalHudVisibilityHook()) {",
    ),
]

for old, new in replacements:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"rc7d dual-HUD expected exactly one source match, got {count}: {old[:120]!r}")
    source = source.replace(old, new, 1)

marker = "void __fastcall HookHudSetVisible(void* element, bool visible)"
addition = r'''void __fastcall HookGlobalHudVisibility(void* flashUI, bool visible)
{
    if (flashUI == g_flashUI && !visible && ShouldHoldConcreteHudVisible()) {
        if (!g_globalHudHideSuppressionObserved.exchange(true, std::memory_order_acq_rel))
            Log("Clean Pause HUD preservation: suppressed IFlashUI::SetHudElementsVisible(false)");
        return;
    }

    if (g_originalSetHudElementsVisible)
        g_originalSetHudElementsVisible(flashUI, visible);
}

bool EnsureGlobalHudVisibilityHook()
{
    if (!g_flashUI || !ValidateObjectVtable(g_flashUI, {kFlashUISetHudElementsVisibleSlot}))
        return false;

    const auto target = reinterpret_cast<void*>(
        VFunc<SetHudElementsVisibleFn>(g_flashUI, kFlashUISetHudElementsVisibleSlot));
    if (!target || !IsExecutable(target))
        return false;

    if (g_setHudElementsVisibleTarget)
        return target == g_setHudElementsVisibleTarget;

    const MH_STATUS create = MH_CreateHook(
        target,
        reinterpret_cast<void*>(&HookGlobalHudVisibility),
        reinterpret_cast<void**>(&g_originalSetHudElementsVisible));
    if (create != MH_OK) {
        Log("MH_CreateHook(IFlashUI SetHudElementsVisible) failed: %d", static_cast<int>(create));
        return false;
    }

    const MH_STATUS enable = MH_EnableHook(target);
    if (enable != MH_OK) {
        Log("MH_EnableHook(IFlashUI SetHudElementsVisible) failed: %d", static_cast<int>(enable));
        return false;
    }

    g_setHudElementsVisibleTarget = target;
    Log("global HUD visibility hook active; flashUI=%p SetHudElementsVisible=%p",
        g_flashUI,
        g_setHudElementsVisibleTarget);
    return true;
}

void __fastcall HookHudSetVisible(void* element, bool visible)'''
count = source.count(marker)
if count != 1:
    raise SystemExit(f"rc7d dual-HUD insertion marker count={count}")
source = source.replace(marker, addition, 1)

required = (
    "HookGlobalHudVisibility",
    "EnsureGlobalHudVisibilityHook",
    "flashUI == g_flashUI && !visible && ShouldHoldConcreteHudVisible()",
    "suppressed IFlashUI::SetHudElementsVisible(false)",
    "g_originalSetHudElementsVisible(flashUI, visible)",
    "EnsureHudVisibilityHook() || !EnsureGlobalHudVisibilityHook()",
    "HookHudSetVisible",
    "SetConcreteHudVisibleAndVerify(true, false)",
    "ReplayVanillaPauseToggle",
)
for needle in required:
    if needle not in source:
        raise SystemExit(f"generated rc7d dual-HUD source missing: {needle}")

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(source, encoding="utf-8")
print(f"generated rc7d dual-HUD source: {out_path}")
