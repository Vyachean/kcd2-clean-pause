from pathlib import Path
import sys

if len(sys.argv) != 3:
    raise SystemExit("usage: generate_candidate_v2.py <input.cpp> <output.cpp>")

source_path = Path(sys.argv[1])
out_path = Path(sys.argv[2])
source = source_path.read_text(encoding="utf-8")

replacements = [
    (
        "std::atomic_bool g_renderSuppressionObserved{false};\nstd::atomic_bool g_swallowPauseRelease{false};\nstd::atomic_bool g_swallowResumeRelease{false};\nstd::atomic_bool g_pendingPauseAttempt{false};\nstd::atomic_ullong g_pendingDeadlineMs{0};",
        "std::atomic_bool g_renderSuppressionObserved{false};\nstd::atomic_ullong g_cleanHiddenSinceMs{0};\nstd::atomic_bool g_hudGateForcedVisible{false};\nstd::atomic_bool g_swallowPauseRelease{false};\nstd::atomic_bool g_swallowResumeRelease{false};\nstd::atomic_bool g_pendingPauseAttempt{false};\nstd::atomic_ullong g_pendingDeadlineMs{0};\nInputEvent g_pausePressTemplate{};\nInputEvent g_pauseReleaseTemplate{};\nbool g_havePausePressTemplate{};\nbool g_havePauseReleaseTemplate{};",
    ),
    (
        "using RenderFn = void(__fastcall*)(void*);\nRenderFn g_originalRender{};\nvoid* g_renderTarget{};",
        "using RenderFn = void(__fastcall*)(void*);\nusing SetHudElementsVisibleFn = void(__fastcall*)(void*, bool);\nusing HudCallFunctionFn = bool(__fastcall*)(void*, const char*, const void*, void*, const char*);\nRenderFn g_originalRender{};\nvoid* g_renderTarget{};\nvoid* g_hudElement{};\nHudCallFunctionFn g_originalHudCallFunction{};\nvoid* g_hudCallFunctionTarget{};",
    ),
    (
        "constexpr ULONGLONG kPendingWindowMs = 750;\nconstexpr std::size_t kUIElementRenderSlot = 24;",
        "constexpr ULONGLONG kPendingWindowMs = 750;\nconstexpr ULONGLONG kRenderObservationGraceMs = 250;\nconstexpr std::size_t kUIElementRenderSlot = 24;\nconstexpr std::size_t kFlashUISetHudElementsVisibleSlot = 28;\nconstexpr std::size_t kUIElementCallFunctionByNameSlot = 69;",
    ),
    (
        "    if (!ValidateObjectVtable(value.flashUI, {kFlashUIGetElementByInstanceStrSlot}))\n        return false;",
        "    if (!ValidateObjectVtable(value.flashUI, {\n            kFlashUIGetElementByInstanceStrSlot,\n            kFlashUISetHudElementsVisibleSlot }))\n        return false;",
    ),
    (
        "    return menu && ValidateObjectVtable(menu, {kUIElementRenderSlot, kUIElementIsVisibleSlot});\n}\n\nvoid __fastcall HookMenuRender(void* element)",
        r'''    return menu && ValidateObjectVtable(menu, {kUIElementRenderSlot, kUIElementIsVisibleSlot});
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

bool SetHudGateVisible(bool visible)
{
    if (!g_flashUI)
        return false;

    const auto setHudVisible =
        VFunc<SetHudElementsVisibleFn>(g_flashUI, kFlashUISetHudElementsVisibleSlot);
    if (!setHudVisible || !IsExecutable(reinterpret_cast<void*>(setHudVisible)))
        return false;

    __try {
        setHudVisible(g_flashUI, visible);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    return true;
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

void __fastcall HookMenuRender(void* element)''',
    ),
    (
        "    g_cleanHidden.store(false, std::memory_order_release);\n    g_renderSuppressionObserved.store(false, std::memory_order_release);\n    g_swallowPauseRelease.store(false, std::memory_order_release);",
        "    g_cleanHidden.store(false, std::memory_order_release);\n    g_renderSuppressionObserved.store(false, std::memory_order_release);\n    g_cleanHiddenSinceMs.store(0, std::memory_order_release);\n    g_hudGateForcedVisible.store(false, std::memory_order_release);\n    g_swallowPauseRelease.store(false, std::memory_order_release);",
    ),
    (
        "void ArmPendingPauseAttempt()\n{",
        r'''bool ReplayVanillaPauseToggle(void* input, bool force)
{
    if (!g_havePausePressTemplate || !g_havePauseReleaseTemplate)
        return false;

    const InputEvent press = g_pausePressTemplate;
    const InputEvent release = g_pauseReleaseTemplate;
    Log("B resume: replaying vanilla pause key=%u press/release through original PostInputEvent",
        static_cast<unsigned>(press.keyId));
    Forward(input, &press, force);
    Forward(input, &release, force);

    bool visible{};
    return ReadVerifiedMenuVisible(visible) && !visible;
}

void ArmPendingPauseAttempt()
{''',
    ),
    (
        "    g_renderSuppressionObserved.store(false, std::memory_order_release);\n    g_cleanHidden.store(true, std::memory_order_release);",
        r'''    if (!SetHudGateVisible(true)) {
        Log("vanilla pause opened but HUD visibility gate could not be restored; leaving ordinary visible pause menu (fail-open)");
        return false;
    }

    g_hudGateForcedVisible.store(true, std::memory_order_release);
    g_renderSuppressionObserved.store(false, std::memory_order_release);
    g_cleanHiddenSinceMs.store(GetTickCount64(), std::memory_order_release);
    g_cleanHidden.store(true, std::memory_order_release);''',
    ),
    (
        "    bool visible{};\n    if (!ReadVerifiedMenuVisible(visible) || !visible) {\n        ClearHiddenState(\"vanilla Menu@0 no longer visible or verification failed\");\n        Forward(input, event, force);\n        return;\n    }",
        r'''    bool visible{};
    if (!ReadVerifiedMenuVisible(visible)) {
        if (g_hudGateForcedVisible.exchange(false, std::memory_order_acq_rel))
            SetHudGateVisible(false);
        ClearHiddenState("vanilla Menu@0 verification failed; ordinary pause presentation restored");
        Forward(input, event, force);
        return;
    }
    if (!visible) {
        g_hudGateForcedVisible.store(false, std::memory_order_release);
        ClearHiddenState("vanilla Menu@0 closed outside Clean Pause");
        Forward(input, event, force);
        return;
    }''',
    ),
    (
        "    if (!g_renderSuppressionObserved.load(std::memory_order_acquire)) {\n        ClearHiddenState(\"Render suppression was not observed before next physical input; fail-open\");\n        Forward(input, event, force);\n        return;\n    }",
        r'''    if (!g_renderSuppressionObserved.load(std::memory_order_acquire)) {
        const ULONGLONG enteredAt = g_cleanHiddenSinceMs.load(std::memory_order_acquire);
        const ULONGLONG now = GetTickCount64();
        if (enteredAt != 0 && now - enteredAt > kRenderObservationGraceMs) {
            if (g_hudGateForcedVisible.exchange(false, std::memory_order_acq_rel))
                SetHudGateVisible(false);
            ClearHiddenState("Render suppression was not observed within 250 ms; fail-open");
            Forward(input, event, force);
            return;
        }
    }''',
    ),
    (
        "        if (pressed) {\n            g_cleanHidden.store(false, std::memory_order_release);\n            g_renderSuppressionObserved.store(false, std::memory_order_release);\n            g_swallowPauseRelease.store(true, std::memory_order_release);",
        r'''        if (pressed) {
            if (g_hudGateForcedVisible.exchange(false, std::memory_order_acq_rel)
                && !SetHudGateVisible(false))
                Log("could not restore vanilla HUD-hidden pause presentation before showing Menu");
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            g_swallowPauseRelease.store(true, std::memory_order_release);''',
    ),
    (
        "    if (key == KeyId::XiB) {\n        Forward(input, event, force);\n\n        bool visibleAfter{};\n        if (!ReadVerifiedMenuVisible(visibleAfter)) {\n            ClearHiddenState(\"Menu visibility verification failed after B; fail-open\");\n            return;\n        }\n\n        if (!visibleAfter) {\n            g_cleanHidden.store(false, std::memory_order_release);\n            g_renderSuppressionObserved.store(false, std::memory_order_release);\n            if (pressed)\n                g_swallowResumeRelease.store(true, std::memory_order_release);\n            Log(\"Clean Pause -> running via vanilla B/back\");\n            return;\n        }\n\n        return;\n    }",
        r'''    if (key == KeyId::XiB) {
        if (released)
            return;
        if (!pressed)
            return;

        if (ReplayVanillaPauseToggle(input, force)) {
            g_cleanHidden.store(false, std::memory_order_release);
            g_renderSuppressionObserved.store(false, std::memory_order_release);
            g_cleanHiddenSinceMs.store(0, std::memory_order_release);
            g_hudGateForcedVisible.store(false, std::memory_order_release);
            g_pendingPauseAttempt.store(false, std::memory_order_release);
            g_pendingDeadlineMs.store(0, std::memory_order_release);
            g_swallowResumeRelease.store(true, std::memory_order_release);
            Log("Clean Pause -> running via B using replayed vanilla pause toggle");
            return;
        }

        if (g_hudGateForcedVisible.exchange(false, std::memory_order_acq_rel))
            SetHudGateVisible(false);
        ClearHiddenState("B resume toggle was not verified; showing ordinary vanilla pause menu (fail-open)");
        g_swallowResumeRelease.store(true, std::memory_order_release);
        return;
    }''',
    ),
    (
        "    const auto key = event->keyId;\n    const bool pressed = (event->state & InputState::Pressed) != 0;\n    const bool released = (event->state & InputState::Released) != 0;\n\n    if (released && key == KeyId::XiB",
        r'''    const auto key = event->keyId;
    const bool pressed = (event->state & InputState::Pressed) != 0;
    const bool released = (event->state & InputState::Released) != 0;

    if (IsPauseKey(key)) {
        if (pressed) {
            g_pausePressTemplate = *event;
            g_havePausePressTemplate = true;
            g_havePauseReleaseTemplate = false;
        }
        if (released && g_havePausePressTemplate
            && g_pausePressTemplate.keyId == key) {
            g_pauseReleaseTemplate = *event;
            g_havePauseReleaseTemplate = true;
        }
    }

    if (g_cleanHidden.load(std::memory_order_acquire) && pressed)
        Log("Clean Pause physical input: key=%u name=%s state=0x%08x",
            static_cast<unsigned>(key),
            event->keyName ? event->keyName : "<null>",
            static_cast<unsigned>(event->state));

    if (released && key == KeyId::XiB''',
    ),
    (
        "        if (!EnsureMenuRenderHook()) {",
        "        if (!EnsureMenuRenderHook() || !EnsureHudSubtitleHook()) {",
    ),
    (
        "            Log(\"pause input: Menu@0 render hook unavailable; leaving vanilla behavior untouched\");",
        "            Log(\"pause input: required Menu/HUD presentation hooks unavailable; leaving vanilla behavior untouched\");",
    ),
    (
        "rc7 render-suppression candidate active; env=%p",
        "rc7c HUD-preserving render-suppression candidate active; env=%p",
    ),
    (
        "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7 render-suppression candidate",
        "native bootstrap started; target=KCD2 1.5.6 Windows retail; rc7c HUD-preserving render-suppression candidate",
    ),
]

for old, new in replacements:
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one source match, got {count}: {old[:100]!r}")
    source = source.replace(old, new, 1)

required = (
    "kRenderObservationGraceMs = 250",
    "kFlashUISetHudElementsVisibleSlot = 28",
    "kUIElementCallFunctionByNameSlot = 69",
    "SetHudGateVisible(true)",
    "ClearSubtitles",
    "HideNarrativeSubtitles",
    "ReplayVanillaPauseToggle",
    "Clean Pause -> running via B using replayed vanilla pause toggle",
    "rc7c HUD-preserving render-suppression candidate active",
)
for needle in required:
    if needle not in source:
        raise SystemExit(f"generated rc7c source missing: {needle}")

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(source, encoding="utf-8")
print(f"generated rc7c source: {out_path}")
