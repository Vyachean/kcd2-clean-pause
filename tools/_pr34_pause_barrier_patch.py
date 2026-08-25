from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one replacement anchor, got {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: str, marker: str, text_to_append: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if marker in text:
        return
    if not text.endswith("\n"):
        text += "\n"
    p.write_text(text + text_to_append, encoding="utf-8")


# ---------------------------------------------------------------------------
# ABI: observe the verified IGame -> IGameFramework surface. We never call
# PauseGame ourselves; the hook only observes vanilla's call/return barrier.
# ---------------------------------------------------------------------------
replace_once(
    "native/src/kcd2_abi.h",
    "inline constexpr std::size_t kGameGetLongNameSlot = 12;\ninline constexpr std::size_t kGameGetNameSlot = 13;\n",
    "inline constexpr std::size_t kGameGetLongNameSlot = 12;\n"
    "inline constexpr std::size_t kGameGetNameSlot = 13;\n"
    "inline constexpr std::size_t kGameGetFrameworkSlot = 16;\n"
    "inline constexpr std::size_t kGameFrameworkPauseGameSlot = 13;\n"
    "inline constexpr std::size_t kGameFrameworkGetSystemSlot = 19;\n",
)
replace_once(
    "native/src/kcd2_abi.h",
    "using PostInputEventFn = void(__fastcall*)(void*, const InputEvent*, bool);\n",
    "using PostInputEventFn = void(__fastcall*)(void*, const InputEvent*, bool);\n"
    "using GetGameFrameworkFn = void*(__fastcall*)(void*);\n"
    "using PauseGameFn = void(__fastcall*)(void*, bool, bool, unsigned int);\n"
    "using GameFrameworkGetSystemFn = void*(__fastcall*)(void*);\n",
)

# ---------------------------------------------------------------------------
# C_UIHudMask: cache the validated concrete objects for the current hud@0.
# Re-run listener/RTTI discovery only when hud@0 is actually recreated.
# ---------------------------------------------------------------------------
replace_once(
    "native/src/clean_pause_hud_mask.cpp",
    "std::atomic<void*> g_maskObject{nullptr};\nstd::atomic<void*> g_sourceMonitorObject{nullptr};\n",
    "std::atomic<void*> g_maskObject{nullptr};\n"
    "std::atomic<void*> g_sourceMonitorObject{nullptr};\n"
    "std::atomic<void*> g_hudElementObject{nullptr};\n",
)
replace_once(
    "native/src/clean_pause_hud_mask.cpp",
    "bool InstallHook(void* target, void* detour, void** original, void*& installedTarget)\n{\n",
    "bool LoadCachedMaskObjects(void* hudElement, void*& mask, void*& sourceMonitor)\n"
    "{\n"
    "    mask = nullptr;\n"
    "    sourceMonitor = nullptr;\n"
    "    if (!hudElement || g_hudElementObject.load(std::memory_order_acquire) != hudElement)\n"
    "        return false;\n\n"
    "    mask = g_maskObject.load(std::memory_order_acquire);\n"
    "    sourceMonitor = g_sourceMonitorObject.load(std::memory_order_acquire);\n"
    "    if (!mask || !sourceMonitor)\n"
    "        return false;\n"
    "    if (!ValidateVtable(mask, kMaskOnModuleMessageSlot)\n"
    "        || !ValidateVtable(sourceMonitor, kSourceEventSlot))\n"
    "        return false;\n"
    "    return true;\n"
    "}\n\n"
    "bool InstallHook(void* target, void* detour, void** original, void*& installedTarget)\n{\n",
)
replace_once(
    "native/src/clean_pause_hud_mask.cpp",
    "    void* mask{};\n    void* sourceMonitor{};\n    if (!FindMaskObjects(hudElement, mask, sourceMonitor))\n        return false;\n\n    const auto sourceTarget = reinterpret_cast<void*>(\n",
    "    void* mask{};\n"
    "    void* sourceMonitor{};\n"
    "    const bool cached = LoadCachedMaskObjects(hudElement, mask, sourceMonitor);\n"
    "    if (!cached && !FindMaskObjects(hudElement, mask, sourceMonitor))\n"
    "        return false;\n\n"
    "    const auto sourceTarget = reinterpret_cast<void*>(\n",
)
replace_once(
    "native/src/clean_pause_hud_mask.cpp",
    "    // Partial installation is inert because the observer is published only after\n    // both mutation paths are hooked successfully.\n    if (!InstallHook(\n",
    "    if (cached && g_sourceEventTarget == sourceTarget\n"
    "        && g_onModuleMessageTarget == moduleMessageTarget) {\n"
    "        g_observer.store(observer, std::memory_order_release);\n"
    "        return true;\n"
    "    }\n\n"
    "    // Partial installation is inert because the observer is published only after\n"
    "    // both mutation paths are hooked successfully.\n"
    "    if (!InstallHook(\n",
)
replace_once(
    "native/src/clean_pause_hud_mask.cpp",
    "    g_maskObject.store(mask, std::memory_order_release);\n    g_sourceMonitorObject.store(sourceMonitor, std::memory_order_release);\n    g_observer.store(observer, std::memory_order_release);\n",
    "    g_maskObject.store(mask, std::memory_order_release);\n"
    "    g_sourceMonitorObject.store(sourceMonitor, std::memory_order_release);\n"
    "    g_hudElementObject.store(hudElement, std::memory_order_release);\n"
    "    g_observer.store(observer, std::memory_order_release);\n",
)
replace_once(
    "native/src/clean_pause_hud_mask.cpp",
    "    void* mask{};\n    void* sourceMonitor{};\n    if (!FindMaskObjects(hudElement, mask, sourceMonitor))\n        return false;\n\n    auto* visibilityInterface = reinterpret_cast<std::uint8_t*>(mask)\n",
    "    void* mask{};\n"
    "    void* sourceMonitor{};\n"
    "    if (!LoadCachedMaskObjects(hudElement, mask, sourceMonitor)\n"
    "        && !FindMaskObjects(hudElement, mask, sourceMonitor))\n"
    "        return false;\n\n"
    "    auto* visibilityInterface = reinterpret_cast<std::uint8_t*>(mask)\n",
)

# ---------------------------------------------------------------------------
# Bubbles: same cache discipline. Resolve Menu cheaply, but do not re-scan the
# hud listener storage when the concrete hud@0 identity did not change.
# ---------------------------------------------------------------------------
replace_once(
    "native/src/clean_pause_bubbles.cpp",
    "std::atomic<void*> g_bubbleInterfaceObject{nullptr};\n",
    "std::atomic<void*> g_bubbleInterfaceObject{nullptr};\n"
    "std::atomic<void*> g_hudElementObject{nullptr};\n",
)
replace_once(
    "native/src/clean_pause_bubbles.cpp",
    "bool EnsureHooks(void* hudElement, void* flashUI)\n{\n    void* menu = ResolveMenu(flashUI);\n    void* bubbleInterface = FindBubbleInterface(hudElement);\n    if (!menu || !bubbleInterface)\n        return false;\n",
    "bool EnsureHooks(void* hudElement, void* flashUI)\n"
    "{\n"
    "    void* menu = ResolveMenu(flashUI);\n"
    "    if (!menu)\n"
    "        return false;\n\n"
    "    void* bubbleInterface{};\n"
    "    const bool cached = g_hudElementObject.load(std::memory_order_acquire) == hudElement\n"
    "        && g_menuElement == menu;\n"
    "    if (cached)\n"
    "        bubbleInterface = g_bubbleInterfaceObject.load(std::memory_order_acquire);\n"
    "    if (!bubbleInterface)\n"
    "        bubbleInterface = FindBubbleInterface(hudElement);\n"
    "    if (!bubbleInterface)\n"
    "        return false;\n",
)
replace_once(
    "native/src/clean_pause_bubbles.cpp",
    "    // Install suppression hooks before the menu-visibility hook. Until the final hook\n",
    "    if (cached\n"
    "        && g_bubbleUpdateTarget == bubbleUpdateTarget\n"
    "        && g_bubbleReleaseTarget == bubbleReleaseTarget\n"
    "        && g_menuSetVisibleTarget == menuSetVisibleTarget)\n"
    "        return true;\n\n"
    "    // Install suppression hooks before the menu-visibility hook. Until the final hook\n",
)
replace_once(
    "native/src/clean_pause_bubbles.cpp",
    "    g_bubbleInterfaceObject.store(bubbleInterface, std::memory_order_release);\n\n    bool visible{};\n",
    "    g_bubbleInterfaceObject.store(bubbleInterface, std::memory_order_release);\n"
    "    g_hudElementObject.store(hudElement, std::memory_order_release);\n\n"
    "    bool visible{};\n",
)

# ---------------------------------------------------------------------------
# Runtime state / pause barrier.
# ---------------------------------------------------------------------------
replace_once(
    "native/src/clean_pause_native.cpp",
    "void* g_game{};\nvoid* g_flashUI{};\n",
    "void* g_game{};\n"
    "void* g_gameFramework{};\n"
    "void* g_flashUI{};\n"
    "PauseGameFn g_originalPauseGame{};\n"
    "void* g_pauseGameTarget{};\n"
    "std::atomic_bool g_pauseBarrierObserved{false};\n",
)
replace_once(
    "native/src/clean_pause_native.cpp",
    "void* g_hudUpdateTarget{};\nstd::atomic_bool g_hudUpdateFirstEntryLogged{false};\n",
    "void* g_hudUpdateTarget{};\n"
    "void* g_hudUpdateElement{};\n"
    "std::atomic_bool g_hudUpdateFirstEntryLogged{false};\n",
)
replace_once(
    "native/src/clean_pause_native.cpp",
    "    if (!ValidateObjectVtable(value.game, {kGameGetLongNameSlot, kGameGetNameSlot}))\n",
    "    if (!ValidateObjectVtable(value.game, {\n"
    "            kGameGetLongNameSlot, kGameGetNameSlot, kGameGetFrameworkSlot }))\n",
)
replace_once(
    "native/src/clean_pause_native.cpp",
    "    g_nextHudSnapshotRefreshMs.store(0, std::memory_order_release);\n}\n",
    "    g_nextHudSnapshotRefreshMs.store(0, std::memory_order_release);\n"
    "    g_pauseBarrierObserved.store(false, std::memory_order_release);\n"
    "}\n",
)

old_ensure_hud_update = '''bool EnsureHudUpdateHook()\n{\n    void* hud{};\n    if (!ResolveHudElement(hud))\n        return false;\n\n    // C_UIHudMask is the source-derived owner of the 28 child visibility flags.\n    // Observe its mutations before vanilla sees Start so a pause-source update can be\n    // visually rolled back in the same call stack, before the next render.\n    bool maskAvailable = hud_mask::EnsureHooks(hud, &ReconcileHudMaskMutation);\n    if (maskAvailable) {\n        bool visibilityProbe[kHudClipCount]{};\n        maskAvailable = hud_mask::ReadCurrentVisibility(\n            hud, visibilityProbe, kHudClipCount);\n    }\n    g_hudMaskTransactionAvailable.store(maskAvailable, std::memory_order_release);\n    if (maskAvailable)\n        Log("C_UIHudMask transaction active for hud=%p", hud);\n    else\n        Log("C_UIHudMask transaction unavailable; using snapshot restore fallback");\n\n    // Overhead NPC subtitles are managed by C_UIHudBubbles below the root "Bubbles"\n    // movieclip. Install their optional lifecycle freeze before vanilla sees Start.\n    // Discovery failure is intentionally ignored so the proven Clean Pause path remains\n    // available even if a storefront/build changes the concrete listener layout.\n    bubbles::EnsureHooks(hud, g_flashUI);\n\n    const auto target = reinterpret_cast<void*>(VFunc<UIElementUpdateFn>(hud, kUIElementUpdateSlot));\n    if (!target || !IsExecutable(target))\n        return false;\n\n    if (g_hudUpdateTarget) {\n        if (target != g_hudUpdateTarget)\n            return false;\n        g_hudElement = hud;\n        return true;\n    }\n\n    g_hudElement = hud;\n    const MH_STATUS create = MH_CreateHook(\n        target,\n        reinterpret_cast<void*>(&HookHudUpdate),\n        reinterpret_cast<void**>(&g_originalHudUpdate));\n    if (create != MH_OK) {\n        Log("MH_CreateHook(HUD Update) failed: %d", static_cast<int>(create));\n        return false;\n    }\n    const MH_STATUS enable = MH_EnableHook(target);\n    if (enable != MH_OK) {\n        Log("MH_EnableHook(HUD Update) failed: %d", static_cast<int>(enable));\n        return false;\n    }\n\n    g_hudUpdateTarget = target;\n    Log("hud@0 main-thread Update hook active; hud=%p Update=%p", g_hudElement, g_hudUpdateTarget);\n    return true;\n}\n'''
new_ensure_hud_update = '''bool EnsureHudUpdateHook()\n{\n    void* hud{};\n    if (!ResolveHudElement(hud))\n        return false;\n\n    const auto target = reinterpret_cast<void*>(VFunc<UIElementUpdateFn>(hud, kUIElementUpdateSlot));\n    if (!target || !IsExecutable(target))\n        return false;\n\n    // The expensive listener/RTTI discovery is tied to one concrete hud@0 lifetime.\n    // Repeated pause presses on the same HUD reuse the already-validated identities.\n    if (g_hudUpdateTarget) {\n        if (target != g_hudUpdateTarget)\n            return false;\n        if (hud == g_hudUpdateElement) {\n            g_hudElement = hud;\n            return true;\n        }\n    }\n\n    // C_UIHudMask is the source-derived owner of the 28 child visibility flags.\n    // Observe its mutations before vanilla sees Start so a pause-source update can be\n    // visually rolled back in the same call stack, before the next render.\n    bool maskAvailable = hud_mask::EnsureHooks(hud, &ReconcileHudMaskMutation);\n    if (maskAvailable) {\n        bool visibilityProbe[kHudClipCount]{};\n        maskAvailable = hud_mask::ReadCurrentVisibility(\n            hud, visibilityProbe, kHudClipCount);\n    }\n    g_hudMaskTransactionAvailable.store(maskAvailable, std::memory_order_release);\n    if (maskAvailable)\n        Log("C_UIHudMask transaction active for hud=%p", hud);\n    else\n        Log("C_UIHudMask transaction unavailable; using snapshot restore fallback");\n\n    // Overhead NPC subtitles are managed by C_UIHudBubbles below the root "Bubbles"\n    // movieclip. Install their optional lifecycle freeze before vanilla sees Start.\n    bubbles::EnsureHooks(hud, g_flashUI);\n\n    g_hudElement = hud;\n    g_hudUpdateElement = hud;\n    if (g_hudUpdateTarget) {\n        Log("hud@0 recreated; cached HUD listener identities retargeted to hud=%p", hud);\n        return true;\n    }\n\n    const MH_STATUS create = MH_CreateHook(\n        target,\n        reinterpret_cast<void*>(&HookHudUpdate),\n        reinterpret_cast<void**>(&g_originalHudUpdate));\n    if (create != MH_OK) {\n        Log("MH_CreateHook(HUD Update) failed: %d", static_cast<int>(create));\n        return false;\n    }\n    const MH_STATUS enable = MH_EnableHook(target);\n    if (enable != MH_OK) {\n        Log("MH_EnableHook(HUD Update) failed: %d", static_cast<int>(enable));\n        return false;\n    }\n\n    g_hudUpdateTarget = target;\n    Log("hud@0 main-thread Update hook active; hud=%p Update=%p", g_hudElement, g_hudUpdateTarget);\n    return true;\n}\n'''
replace_once("native/src/clean_pause_native.cpp", old_ensure_hud_update, new_ensure_hud_update)

replace_once(
    "native/src/clean_pause_native.cpp",
    "bool TryEnterCleanPause(const char* trigger, bool swallowMatchingRelease)\n{\n    bool visible{};\n    if (!ReadVerifiedMenuVisible(visible) || !visible)\n        return false;\n",
    "bool TryEnterCleanPause(\n"
    "    const char* trigger,\n"
    "    bool swallowMatchingRelease,\n"
    "    bool requireMenuVisible = true)\n"
    "{\n"
    "    if (requireMenuVisible) {\n"
    "        bool visible{};\n"
    "        if (!ReadVerifiedMenuVisible(visible) || !visible)\n"
    "            return false;\n"
    "    } else if (!g_menuElement || !g_renderTarget) {\n"
    "        return false;\n"
    "    }\n",
)

pressed_old = '''        ArmPendingPauseAttempt();\n        Forward(input, event, force);\n        if (!TryEnterCleanPause("Escape/Start press", true)\n            && g_gameplayHudSnapshot.captured)\n            ArmPendingPauseAttempt();\n        return;\n'''
pressed_new = '''        ArmPendingPauseAttempt();\n        g_pauseBarrierObserved.store(false, std::memory_order_release);\n        Forward(input, event, force);\n\n        // Preferred path: vanilla itself called and returned from PauseGame(true)\n        // while handling this physical press. We are now outside the nested vanilla\n        // input stack but still in the same PostInputEvent call, so presentation can\n        // be accepted without waiting for the physical Start/Escape release or for a\n        // visible Menu frame. The release is swallowed after successful ownership.\n        if (g_pauseBarrierObserved.exchange(false, std::memory_order_acq_rel)) {\n            if (!TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)\n                && g_gameplayHudSnapshot.captured)\n                ArmPendingPauseAttempt();\n            return;\n        }\n\n        // Compatibility fallback when the verified engine barrier was not observed.\n        if (!TryEnterCleanPause("Escape/Start press", true)\n            && g_gameplayHudSnapshot.captured)\n            ArmPendingPauseAttempt();\n        return;\n'''
replace_once("native/src/clean_pause_native.cpp", pressed_old, pressed_new)

install_anchor = '''bool InstallInputHook(const RuntimeEnvironment& environment)\n{\n'''
barrier_code = '''bool ResolveGameFramework(const RuntimeEnvironment& environment, void*& framework)\n{\n    framework = nullptr;\n    if (!environment.game || !environment.system\n        || !ValidateObjectVtable(environment.game, {kGameGetFrameworkSlot}))\n        return false;\n\n    const auto getFramework = VFunc<GetGameFrameworkFn>(\n        environment.game, kGameGetFrameworkSlot);\n    if (!getFramework || !IsExecutable(reinterpret_cast<void*>(getFramework)))\n        return false;\n\n    __try {\n        framework = getFramework(environment.game);\n    } __except (EXCEPTION_EXECUTE_HANDLER) {\n        framework = nullptr;\n    }\n    if (!framework || !ValidateObjectVtable(framework, {\n            kGameFrameworkPauseGameSlot, kGameFrameworkGetSystemSlot }))\n        return false;\n\n    // Identity proof: slot 19 is the verified IGameFramework::GetISystem accessor.\n    // Do not hook a merely shape-compatible object whose system does not match gEnv.\n    const auto getSystem = VFunc<GameFrameworkGetSystemFn>(\n        framework, kGameFrameworkGetSystemSlot);\n    void* frameworkSystem{};\n    __try {\n        frameworkSystem = getSystem ? getSystem(framework) : nullptr;\n    } __except (EXCEPTION_EXECUTE_HANDLER) {\n        frameworkSystem = nullptr;\n    }\n    return frameworkSystem == environment.system;\n}\n\nvoid __fastcall HookPauseGame(\n    void* framework,\n    bool pause,\n    bool force,\n    unsigned int fadeOutInMs)\n{\n    const bool observe = framework == g_gameFramework\n        && pause\n        && g_pendingPauseAttempt.load(std::memory_order_acquire)\n        && (!g_mainThreadId || GetCurrentThreadId() == g_mainThreadId);\n    const ULONGLONG enteredAt = observe ? GetTickCount64() : 0;\n\n    // KCD2 remains the only pause owner. Never alter arguments and never synthesize a\n    // PauseGame call; observe only after the exact vanilla call has returned.\n    if (g_originalPauseGame)\n        g_originalPauseGame(framework, pause, force, fadeOutInMs);\n\n    if (!observe || !g_pendingPauseAttempt.load(std::memory_order_acquire))\n        return;\n\n    g_pauseBarrierObserved.store(true, std::memory_order_release);\n    Log(\n        "vanilla IGameFramework::PauseGame(true) returned during pending pause; force=%s fadeMs=%u callMs=%llu",\n        force ? "true" : "false",\n        fadeOutInMs,\n        static_cast<unsigned long long>(GetTickCount64() - enteredAt));\n}\n\nbool InstallPauseBarrierHook(const RuntimeEnvironment& environment)\n{\n    void* framework{};\n    if (!ResolveGameFramework(environment, framework)) {\n        Log("IGameFramework pause barrier unavailable: verified framework identity could not be resolved");\n        return false;\n    }\n\n    const auto target = reinterpret_cast<void*>(\n        VFunc<PauseGameFn>(framework, kGameFrameworkPauseGameSlot));\n    if (!target || !IsExecutable(target))\n        return false;\n\n    if (g_pauseGameTarget) {\n        if (target != g_pauseGameTarget)\n            return false;\n        g_gameFramework = framework;\n        return true;\n    }\n\n    const MH_STATUS create = MH_CreateHook(\n        target,\n        reinterpret_cast<void*>(&HookPauseGame),\n        reinterpret_cast<void**>(&g_originalPauseGame));\n    if (create != MH_OK) {\n        Log("MH_CreateHook(IGameFramework::PauseGame) failed: %d", static_cast<int>(create));\n        return false;\n    }\n    const MH_STATUS enable = MH_EnableHook(target);\n    if (enable != MH_OK) {\n        MH_RemoveHook(target);\n        Log("MH_EnableHook(IGameFramework::PauseGame) failed: %d", static_cast<int>(enable));\n        return false;\n    }\n\n    g_gameFramework = framework;\n    g_pauseGameTarget = target;\n    Log("vanilla IGameFramework::PauseGame observer active; framework=%p PauseGame=%p",\n        g_gameFramework, g_pauseGameTarget);\n    return true;\n}\n\n'''
replace_once("native/src/clean_pause_native.cpp", install_anchor, barrier_code + install_anchor)

replace_once(
    "native/src/clean_pause_native.cpp",
    "    const MH_STATUS create = MH_CreateHook(\n        g_postInputEventTarget,\n",
    "    // Optional event-driven pause barrier. If it cannot be validated, the existing\n"
    "    Menu visibility path remains the fail-open compatibility behavior.\n"
    "    InstallPauseBarrierHook(environment);\n\n"
    "    const MH_STATUS create = MH_CreateHook(\n"
    "        g_postInputEventTarget,\n",
)

# ---------------------------------------------------------------------------
# Validator: observation of a fully validated vanilla PauseGame call is allowed;
# custom PauseGame ownership/calls remain forbidden by contract tests below.
# ---------------------------------------------------------------------------
replace_once(
    "tools/validate_native_contract.py",
    '    "kGameFrameworkPauseGameSlot",\n    "PauseGameFn",\n',
    "",
)
replace_once(
    "tools/validate_native_contract.py",
    '    "LogWhGameFingerprint",\n',
    '    "LogWhGameFingerprint",\n'
    '    "ResolveGameFramework",\n'
    '    "HookPauseGame",\n'
    '    "InstallPauseBarrierHook",\n'
    '    "g_pauseBarrierObserved",\n',
)
replace_once(
    "tools/validate_native_contract.py",
    '    "kFlashVariableSetVisibleSlot = 33",\n',
    '    "kFlashVariableSetVisibleSlot = 33",\n'
    '    "kGameGetFrameworkSlot = 16",\n'
    '    "kGameFrameworkPauseGameSlot = 13",\n'
    '    "kGameFrameworkGetSystemSlot = 19",\n',
)
append_once(
    "tools/validate_native_contract.py",
    "# pause-barrier ownership contract",
    '''\n# pause-barrier ownership contract\npause_hook = native[native.index("void __fastcall HookPauseGame"):native.index("bool InstallPauseBarrierHook")]\nif pause_hook.index("g_originalPauseGame(") > pause_hook.index("g_pauseBarrierObserved.store(true"):\n    raise SystemExit("PauseGame barrier must be published only after vanilla PauseGame returns")\nif "g_originalPauseGame(framework, pause, force, fadeOutInMs);" not in pause_hook:\n    raise SystemExit("PauseGame observer must forward vanilla arguments unchanged")\nif "g_pendingPauseAttempt.load" not in pause_hook or "framework == g_gameFramework" not in pause_hook:\n    raise SystemExit("PauseGame observer must be scoped to target framework + pending physical pause")\nresolver = native[native.index("bool ResolveGameFramework"):native.index("void __fastcall HookPauseGame")]\nif "kGameGetFrameworkSlot" not in resolver or "kGameFrameworkGetSystemSlot" not in resolver:\n    raise SystemExit("framework discovery must use the verified IGame/IGameFramework accessors")\nif "frameworkSystem == environment.system" not in resolver:\n    raise SystemExit("framework identity must be proven against gEnv ISystem")\npost = native[native.index("void __fastcall HookPostInputEvent"):native.index("bool ResolveGameFramework")]\nbarrier_exchange = post.index("g_pauseBarrierObserved.exchange(false")\nforward_press = post.rfind("Forward(input, event, force);", 0, barrier_exchange)\nif forward_press < 0 or forward_press > barrier_exchange:\n    raise SystemExit("PauseGame barrier may be consumed only after the outer vanilla press dispatch returns")\nif 'TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)' not in post:\n    raise SystemExit("verified PauseGame barrier must accept Clean Pause without waiting for Menu visibility/release")\nif "g_originalPauseGame(" not in native:\n    raise SystemExit("missing vanilla PauseGame forwarding call")\n# The only direct PauseGame call in production must be the trampoline forward inside the detour.\nif native.count("g_originalPauseGame(") != 1:\n    raise SystemExit("production must never synthesize its own PauseGame calls")\n\nprint("pause barrier contract passed")\n''',
)

# ---------------------------------------------------------------------------
# Focused source contract test.
# ---------------------------------------------------------------------------
(ROOT / "tests/test_pause_barrier_contract.py").write_text(r'''import unittest\nfrom pathlib import Path\n\nROOT = Path(__file__).resolve().parents[1]\nNATIVE = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")\nABI = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")\nMASK = (ROOT / "native/src/clean_pause_hud_mask.cpp").read_text(encoding="utf-8")\nBUBBLES = (ROOT / "native/src/clean_pause_bubbles.cpp").read_text(encoding="utf-8")\n\n\nclass PauseBarrierContractTests(unittest.TestCase):\n    def test_verified_framework_surface_is_declared(self):\n        for needle in (\n            "kGameGetFrameworkSlot = 16",\n            "kGameFrameworkPauseGameSlot = 13",\n            "kGameFrameworkGetSystemSlot = 19",\n            "using PauseGameFn =",\n        ):\n            self.assertIn(needle, ABI)\n\n    def test_framework_identity_is_not_shape_only(self):\n        resolver = NATIVE[NATIVE.index("bool ResolveGameFramework"):NATIVE.index("void __fastcall HookPauseGame")]\n        self.assertIn("frameworkSystem == environment.system", resolver)\n        self.assertIn("kGameGetFrameworkSlot", resolver)\n        self.assertIn("kGameFrameworkGetSystemSlot", resolver)\n\n    def test_pause_hook_is_observer_only_and_after_original(self):\n        hook = NATIVE[NATIVE.index("void __fastcall HookPauseGame"):NATIVE.index("bool InstallPauseBarrierHook")]\n        self.assertIn("framework == g_gameFramework", hook)\n        self.assertIn("g_pendingPauseAttempt.load", hook)\n        self.assertLess(hook.index("g_originalPauseGame("), hook.index("g_pauseBarrierObserved.store(true"))\n        self.assertEqual(NATIVE.count("g_originalPauseGame("), 1)\n\n    def test_barrier_consumed_after_outer_press_forward(self):\n        post = NATIVE[NATIVE.index("void __fastcall HookPostInputEvent"):NATIVE.index("bool ResolveGameFramework")]\n        barrier = post.index("g_pauseBarrierObserved.exchange(false")\n        self.assertGreater(post.rfind("Forward(input, event, force);", 0, barrier), -1)\n        self.assertIn(\n            'TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)',\n            post,\n        )\n        self.assertIn("Compatibility fallback", post)\n\n    def test_cached_hud_discovery_is_scoped_to_hud_identity(self):\n        self.assertIn("g_hudElementObject", MASK)\n        self.assertIn("LoadCachedMaskObjects", MASK)\n        self.assertIn("g_hudElementObject.load(std::memory_order_acquire) != hudElement", MASK)\n        self.assertIn("g_hudElementObject", BUBBLES)\n        self.assertIn("g_hudElementObject.load(std::memory_order_acquire) == hudElement", BUBBLES)\n        self.assertIn("hud == g_hudUpdateElement", NATIVE)\n\n\nif __name__ == "__main__":\n    unittest.main()\n'''.replace("\\n", "\n"), encoding="utf-8")

# ---------------------------------------------------------------------------
# Docs: distinguish observing a verified vanilla pause barrier from owning pause.
# ---------------------------------------------------------------------------
replace_once(
    "docs/REJECTED_HYPOTHESES.md",
    "- inferred native `PauseGame` ABI;\n",
    "- calling an inferred/native `PauseGame` as a custom pause owner;\n",
)
replace_once(
    "docs/REJECTED_HYPOTHESES.md",
    "- real Escape/Start is forwarded;\n- `Menu@0::IsVisible()` is the retail lifecycle signal;\n",
    "- real Escape/Start is forwarded;\n"
    "- the verified vanilla `IGameFramework::PauseGame(true, ...)` return may be observed as an event barrier, but is never called by the mod;\n"
    "- `Menu@0::IsVisible()` remains the visible-menu/fail-open lifecycle signal;\n",
)
replace_once(
    "docs/DESIGN.md",
    "1. forwards the physical Escape/Start event to vanilla KCD2;\n2. independently verifies the pause lifecycle via `Menu@0::IsVisible()`;\n3. leaves `Menu@0` logically visible;\n4. suppresses only `Menu@0::Render()` while Clean Pause is active.\n",
    "1. forwards the physical Escape/Start event to vanilla KCD2;\n"
    "2. observes the validated vanilla `IGameFramework::PauseGame(true, ...)` return as the preferred event barrier; the mod never calls `PauseGame` itself and never changes its arguments;\n"
    "3. accepts presentation ownership immediately after the outer physical press dispatch returns when that barrier was observed, instead of waiting for Start/Escape release;\n"
    "4. uses `Menu@0::IsVisible()` as the visible-menu/fail-open lifecycle signal when the barrier is unavailable;\n"
    "5. leaves `Menu@0` logically visible;\n"
    "6. suppresses only `Menu@0::Render()` while Clean Pause is active.\n",
)
replace_once(
    "docs/DESIGN.md",
    "The mask transaction can begin while pause entry is still pending, before `Menu@0` becomes verifiably visible. If that pending attempt expires and no further input arrives, the already-established main-thread `hud@0::Update(float)` path performs rollback to KCD2's vanilla HUD presentation and clears the pending transaction. It does not use update timing to manufacture or retry pause ownership.\n",
    "The mask transaction can begin while pause entry is still pending, before `Menu@0` becomes verifiably visible. The preferred completion point is the return from KCD2's own validated `IGameFramework::PauseGame(true, ...)` call during the forwarded physical press. The detour only records that barrier; Clean Pause presentation is accepted after the outer `PostInputEvent` forwarding returns, avoiding re-entrant Flash/Lua work inside `PauseGame` itself. If no verified barrier is observed, the existing Menu-visibility path remains the compatibility fallback. If the pending attempt expires and no further input arrives, the already-established main-thread `hud@0::Update(float)` path performs rollback to KCD2's vanilla HUD presentation and clears the pending transaction. It does not use update timing to manufacture or retry pause ownership.\n",
)
replace_once(
    "docs/DESIGN.md",
    "SSystemGlobalEnvironment + 0x140     -> IFlashUI*\nIInput::PostInputEvent               -> slot 13\n",
    "SSystemGlobalEnvironment + 0x140     -> IFlashUI*\n"
    "IGame::Get framework/root accessor   -> slot 16\n"
    "IGameFramework::PauseGame            -> slot 13 (observer only)\n"
    "IGameFramework::GetISystem           -> slot 19 (identity proof)\n"
    "IInput::PostInputEvent               -> slot 13\n",
)
replace_once(
    "docs/DESIGN.md",
    "Production does not use custom `PauseGame` ownership, `only_ui` ownership checks,",
    "Production does not use custom `PauseGame` ownership or synthesized `PauseGame` calls, `only_ui` ownership checks,",
)

# Remove this one-shot helper before the workflow commits the product change.
Path(__file__).unlink()
print("PR34 pause barrier patch applied")
