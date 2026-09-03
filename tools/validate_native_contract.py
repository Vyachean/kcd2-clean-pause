from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
native = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
blur = (ROOT / "native/src/clean_pause_blur.cpp").read_text(encoding="utf-8")
mask = (ROOT / "native/src/clean_pause_hud_mask.cpp").read_text(encoding="utf-8")
mask_header = (ROOT / "native/src/clean_pause_hud_mask.h").read_text(encoding="utf-8")
bubbles = (ROOT / "native/src/clean_pause_bubbles.cpp").read_text(encoding="utf-8")
abi = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")
cmake = (ROOT / "native/CMakeLists.txt").read_text(encoding="utf-8")

forbidden = (
    "ActionMapManager.InitActionMaps(",
    "ActionMapManager.LoadFromXML(",
    "Player.OnAction =",
    'ActionMapManager.IsFilterEnabled("only_ui")',
    "HideVerifiedVanillaPause(",
    "SetMenuVisible(false)",
    "ReplayVanillaPauseToggle",
    "g_pausePressTemplate",
    "g_pauseReleaseTemplate",
    "g_havePausePressTemplate",
    "g_havePauseReleaseTemplate",
    "ReleaseFlashVariable",
    "snapshot.clip",
    "0x492D7F8",
    "0x549D388",
    "CryAction.PauseGame(",
    "Action.PauseGame(",
    "Game.PauseGame(",
    "System.GetCVarValue",
)
for needle in forbidden:
    if needle in native or needle in blur or needle in abi or needle in mask or needle in bubbles:
        raise SystemExit(f"forbidden production path: {needle}")

required_abi = (
    "kEnvGameOffset = 0x98",
    "kEnvFlashUIOffset = 0x140",
    "kInputPostInputEventSlot = 13",
    "kScriptExecuteBufferSlot = 6",
    "using ExecuteBufferFn =",
    "kFlashUIGetElementByInstanceStrSlot = 18",
    "kUIElementUpdateSlot = 23",
    "kUIElementSetVisibleSlot = 28",
    "kUIElementIsVisibleSlot = 29",
    "kUIElementGetMovieClipByNameSlot = 71",
    "kFlashVariableGetDisplayInfoSlot = 26",
    "kFlashVariableSetVisibleSlot = 33",
    "kGameFrameworkPauseGameSlot = 13",
    "kGameFrameworkGetSystemSlot = 19",
    "XiStart = 516",
    "XiA = 526",
    "XiB = 527",
)
for needle in required_abi:
    if needle not in abi:
        raise SystemExit(f"missing verified ABI contract: {needle}")

if "kGameGetFrameworkSlot" in abi or "GetGameFrameworkFn" in abi:
    raise SystemExit("legacy IGame[16] framework ABI must not remain in production")

required_runtime = (
    'getElement(g_flashUI, "Menu@0")',
    'getElement(g_flashUI, "hud@0")',
    "HookMenuRender",
    "HookHudUpdate",
    "CaptureHudVisibilitySnapshot",
    "RestoreHudVisibilitySnapshot",
    "RestoreVanillaHudPresentation",
    "HudVisibilitySnapshot g_gameplayHudSnapshot",
    "HudVisibilitySnapshot g_vanillaPauseHudSnapshot",
    "ShouldFreezeHudFunction",
    'std::strcmp(name, "ClearSubtitles") == 0',
    'std::strcmp(name, "HideNarrativeSubtitles") == 0',
    "g_forwardDepth",
    "if (g_forwardDepth != 0)",
    "visible vanilla pause menu via B",
    "blur::Initialize(environment.scriptSystem, environment.mainThreadId)",
    "if (!blur::Disable())",
    "RestoreBlurBestEffort",
    "CLEAN_PAUSE_VERSION",
    "CLEAN_PAUSE_BUILD_ID",
    "kcd2::runtime::ReadBuildIdentity(whGame, identity)",
    "TimeDateStamp=0x%08lx SizeOfImage=0x%08lx CheckSum=0x%08lx",
    "ResolveGameFramework",
    "HookPauseGame",
    "InstallPauseBarrierHook",
    "g_pauseBarrierObserved",
)
for needle in required_runtime:
    if needle not in native:
        raise SystemExit(f"missing production runtime contract: {needle}")
if "KCD2 Clean Pause v0.1.0 active" in native:
    raise SystemExit("runtime identity must not be hard-coded to historical v0.1.0")
for needle in ('../VERSION', 'rev-parse --short=12 HEAD', 'CLEAN_PAUSE_VERSION=', 'CLEAN_PAUSE_BUILD_ID='):
    if needle not in cmake:
        raise SystemExit(f"missing runtime build identity contract: {needle}")

required_mask = (
    '.?AVC_UIHudMask@guimodule@wh@@',
    'kHudListenersOffset = 0x1D0',
    'kMaskListenerOffset = 0x10',
    'kMaskVisibilityInterfaceOffset = 0x58',
    'kMaskSourceMonitorOffset = 0x60',
    'kMaskIsElementVisibleSlot = 1',
    'kModuleMessageIdOffset = 0x08',
    'kHudRefreshModuleMessageId = 52',
    'ReadCurrentVisibility',
    'VFunc<IsElementVisibleFn>',
)
for needle in required_mask:
    if needle not in mask and needle not in mask_header:
        raise SystemExit(f"missing HUD-mask transaction contract: {needle}")
for forbidden_rva in ("0x548BFA8", "0x180555978", "0x180C3BE68"):
    if forbidden_rva in mask:
        raise SystemExit(f"HUD-mask runtime must not depend on fixed WHGame RVA: {forbidden_rva}")

module_hook = mask[mask.index("void __fastcall HookOnModuleMessage"):mask.index("} // namespace\n\nbool EnsureHooks")]
if module_hook.index("IsHudRefreshMessage(message)") > module_hook.index("g_originalOnModuleMessage"):
    raise SystemExit("module message id must be read before vanilla may release/alter the message")
if "if (refresh)\n        NotifyAfterMutation();" not in module_hook:
    raise SystemExit("OnModuleMessage observer must run only for verified HUD refresh message 52")
for needle in (
    "std::atomic<void*> g_maskObject{nullptr};",
    "std::atomic<void*> g_sourceMonitorObject{nullptr};",
    "mask == g_maskObject.load",
    "sourceMonitor == g_sourceMonitorObject.load",
):
    if needle not in mask:
        raise SystemExit(f"global HUD-mask method hook is not target-instance scoped: {needle}")
ensure_mask = mask[mask.index("bool EnsureHooks"):mask.index("bool ReadCurrentVisibility")]
if ensure_mask.index("g_maskObject.store") > ensure_mask.rindex("g_observer.store"):
    raise SystemExit("target HUD-mask identity must be published before initial mutation observer activation")
if ensure_mask.index("g_sourceMonitorObject.store") > ensure_mask.rindex("g_observer.store"):
    raise SystemExit("target source-monitor identity must be published before initial mutation observer activation")

transaction = native[native.index("void ReconcileHudMaskMutation"):native.index("void FailOpenHudMaintenance")]
if "CaptureHudVisibilitySnapshot" in transaction:
    raise SystemExit("partial HUD-mask callbacks must not snapshot the whole Flash HUD as vanilla state")
if "CaptureVanillaHudFromInternalMask" not in transaction or "g_vanillaPauseHudSnapshot = vanillaState;" not in transaction:
    raise SystemExit("HUD-mask callback must retain an authoritative internal-state fallback snapshot")
if "RestoreHudVisibilitySnapshot(g_gameplayHudSnapshot" not in transaction:
    raise SystemExit("HUD-mask mutation must restore the gameplay presentation before render")
if transaction.index("GetCurrentThreadId()") > transaction.index("ShouldPinGameplayHudPresentation()"):
    raise SystemExit("HUD-mask callback must validate thread before reading non-atomic snapshot state")
if "if (!CaptureVanillaHudFromInternalMask(vanillaState))" not in transaction:
    raise SystemExit("HUD-mask visual replay must require a fresh authoritative internal snapshot")
if "fallback.captured ? &fallback : nullptr" not in transaction or "FailOpenHudMaskTransaction(&vanillaState" not in transaction:
    raise SystemExit("HUD-mask transaction must fail open with the best complete internal fallback")

required_blur = (
    'System.GetCVar("wh_cl_NearDof")',
    'System.GetCVar("r_DepthOfField")',
    'System.SetCVar("wh_cl_NearDof", 0)',
    'System.SetCVar("r_DepthOfField", 0)',
    'System.SetCVar("wh_cl_NearDof", __kcd2_clean_pause_prev_near_dof)',
    'System.SetCVar("r_DepthOfField", __kcd2_clean_pause_prev_depth_of_field)',
    "g_suppressed.store(true",
    "disable_blur_rollback",
)
for needle in required_blur:
    if needle not in blur:
        raise SystemExit(f"missing Clean Pause blur lifecycle contract: {needle}")

start = native.index("const char* const kHudClipNames")
end = native.index("};", start)
table = native[start:end]
if table.count('"') != 56:
    raise SystemExit("HUD child snapshot table must contain exactly 28 names")
for name in ("Subtitles", "Hints"):
    if f'"{name}"' not in table:
        raise SystemExit(f"HUD child snapshot table missing {name}")

capture = native[native.index("bool CaptureHudVisibilitySnapshot"):native.index("bool RestoreHudVisibilitySnapshot")]
restore = native[native.index("bool RestoreHudVisibilitySnapshot"):native.index("bool ShouldPinGameplayHudPresentation")]
for block, label in ((capture, "capture"), (restore, "restore")):
    if "getMovieClip(hud, kHudClipNames[i], nullptr)" not in block:
        raise SystemExit(f"{label} does not acquire HUD children through GetMovieClip")
    if "Release" in block:
        raise SystemExit(f"{label} must not Release borrowed GetMovieClip results")
if "info[kFlashDisplayInfoVisibleOffset] != 0" not in capture:
    raise SystemExit("capture must preserve exact pre-transition visibility")
if "setVisible(clip, snapshot.visible[i])" not in restore:
    raise SystemExit("restore must replay captured visibility, not force all children visible")
if "bool rootVisible{};" not in native[native.index("struct HudVisibilitySnapshot"):native.index("HudVisibilitySnapshot g_gameplayHudSnapshot")]:
    raise SystemExit("HUD snapshot must preserve root hud@0 visibility")
for needle in (
    "next.rootVisible = rootVisible;",
    "target.rootVisible = rootVisible;",
    "if (currentRootVisible && !snapshot.rootVisible)",
    "if (!currentRootVisible && snapshot.rootVisible)",
):
    if needle not in native:
        raise SystemExit(f"exact root HUD visibility contract missing: {needle}")

for needle in (
    "std::atomic<void*> g_bubbleInterfaceObject{nullptr};",
    "bubbles == g_bubbleInterfaceObject.load",
    "g_bubbleInterfaceObject.store(bubbleInterface",
):
    if needle not in bubbles:
        raise SystemExit(f"global bubble method hook is not target-instance scoped: {needle}")

menu = native[native.index("void __fastcall HookMenuRender"):native.index("bool EnsureMenuRenderHook")]
for needle in ("GetMovieClip", "RestoreHudVisibilitySnapshot", "SetVisible", "Release"):
    if needle in menu:
        raise SystemExit(f"Menu Render hook performs forbidden HUD lifecycle work: {needle}")
if "g_originalRender(element);" not in menu:
    raise SystemExit("Menu Render hook must forward all non-suppressed renders")

freeze = native[native.index("bool ShouldFreezeHudFunction"):native.index("bool __fastcall HookHudCallFunction")]
if freeze.count("std::strcmp(") != 2:
    raise SystemExit("subtitle freeze whitelist must contain exactly two comparisons")
if "g_pauseTransitionActive.load" not in freeze or "g_pendingPauseAttempt.load" in freeze:
    raise SystemExit("subtitle freeze must be scoped to actual PauseGame transition, not pending input correlation")
pin = native[native.index("bool ShouldPinGameplayHudPresentation"):native.index("bool CaptureVanillaHudFromInternalMask")]
if "g_pauseTransitionActive.load" not in pin or "g_pendingPauseAttempt.load" in pin:
    raise SystemExit("HUD pinning must be scoped to actual PauseGame transition, not pending input correlation")

enter = native[native.index("bool TryEnterCleanPause"):native.index("void HandleHiddenInput")]
if enter.index("if (!blur::Disable())") > enter.index("g_cleanHidden.store(true"):
    raise SystemExit("DoF must be disabled before Clean Pause render ownership begins")
if "const bool transactional" not in enter or "if (!transactional" not in enter:
    raise SystemExit("vanilla Flash snapshot may be required only in non-transaction fallback mode")
entry_transactional = enter[enter.index("if (transactional)"):enter.index("if (!transactional")]
if "if (!CaptureVanillaHudFromInternalMask(currentVanilla))" not in entry_transactional or "return false;" not in entry_transactional:
    raise SystemExit("transactional Clean Pause entry must require fresh internal HUD state")

hidden = native[native.index("void HandleHiddenInput"):native.index("void __fastcall HookPostInputEvent")]
b_start = hidden.index("if (key == KeyId::XiB)")
b_end = hidden.index("// Once a real Menu@0 render", b_start)
b_block = hidden[b_start:b_end]
if "Forward(input, event, force);" in b_block:
    raise SystemExit("physical B must not leak to gameplay/dialog/cutscene")
if "visible vanilla pause menu via B" not in b_block:
    raise SystemExit("B contract must reveal the vanilla pause menu")
if b_block.index("g_hudMaskPinSuspended.store(true") > b_block.index("RestoreVanillaHudPresentation"):
    raise SystemExit("B handoff must suspend all HUD repinning before vanilla restore")
if b_block.index("RestoreBlurBestEffort") > b_block.index("g_cleanHidden.store(false"):
    raise SystemExit("B handoff must restore DoF before visible vanilla presentation")

hud_update = native[native.index("void __fastcall HookHudUpdate"):native.index("bool EnsureHudUpdateHook")]
if "g_hudMaskPinSuspended.load(std::memory_order_acquire)" not in hud_update:
    raise SystemExit("periodic HUD fallback must honor transactional exit suspension")
for needle in (
    "g_pendingPauseAttempt.load(std::memory_order_acquire)",
    "now > deadline",
    'RestoreVanillaHudPresentation("vanilla-pending-timeout-update")',
):
    if needle not in hud_update:
        raise SystemExit(f"pending no-input timeout cleanup missing from HUD update: {needle}")

pending = native[native.index("bool PendingAttemptAlive"):native.index("bool TryEnterCleanPause")]
if pending.index("RestoreVanillaHudPresentation") > pending.index("ResetHudSnapshots"):
    raise SystemExit("pending-entry expiry must undo any pre-ownership visual pin before reset")

post = native[native.index("void __fastcall HookPostInputEvent"):native.index("bool InstallInputHook")]
if post.count("&& g_gameplayHudSnapshot.captured)\n            ArmPendingPauseAttempt();") != 2:
    raise SystemExit("terminal Clean Pause entry failures must not re-arm pending ownership")

print("stable native Clean Pause contract passed")

# pause-barrier ownership contract
pause_hook = native[native.index("void __fastcall HookPauseGame"):native.index("bool InstallPauseBarrierHook")]
if pause_hook.index("g_originalPauseGame(") > pause_hook.index("g_pauseBarrierObserved.store(true"):
    raise SystemExit("PauseGame barrier must be published only after vanilla PauseGame returns")
if "g_pauseTransitionActive.store(true" not in pause_hook:
    raise SystemExit("HUD transaction must arm only when the verified vanilla PauseGame call begins")
if "if (!g_originalPauseGame)" not in pause_hook:
    raise SystemExit("PauseGame observer must fail open if its vanilla trampoline is unavailable")
if "g_originalPauseGame(framework, pause, force, fadeOutInMs);" not in pause_hook:
    raise SystemExit("PauseGame observer must forward exact vanilla arguments unchanged")
if "effectiveFadeOutInMs" in pause_hook:
    raise SystemExit("disproven audio-fade override must not remain in production")
if pause_hook.index("g_pauseTransitionActive.store(true") > pause_hook.index("g_originalPauseGame("):
    raise SystemExit("pause transition pinning must arm before vanilla PauseGame mutates HUD")
if "g_pendingPauseAttempt.load" not in pause_hook or "framework == g_gameFramework" not in pause_hook:
    raise SystemExit("PauseGame observer must be scoped to target framework + pending physical pause")

profile_framework_resolver = native[
    native.index("bool ResolveProfileFramework"):
    native.index("bool ResolveGameFramework")
]
for needle in (
    "FrameworkLocatorStrategy::ExactPointerStorageRva",
    "expectedFrameworkRva",
    "expectedFrameworkVtableRva",
    "kGameFrameworkGetSystemSlot",
    "frameworkSystem != environment.system",
):
    if needle not in profile_framework_resolver:
        raise SystemExit(f"profile framework identity contract missing: {needle}")
if "Storefront::Steam" in profile_framework_resolver:
    raise SystemExit("profile framework resolver must not branch on storefront")
if "kGameGetFrameworkSlot" in profile_framework_resolver:
    raise SystemExit("profile framework resolver must not use legacy IGame[16]")

for needle in (
    "FrameworkLocatorStrategy::ExactPointerStorageRva",
    "FrameworkLocatorStrategy::ExactObjectRva",
    "FrameworkLocatorStrategy::None",
):
    if needle not in profile_framework_resolver:
        raise SystemExit(f"framework locator strategy contract missing: {needle}")

dispatcher = native[
    native.index("bool ResolveGameFramework"):
    native.index("bool ShouldSuppressProfileHudRootVisibility")
]
if "return ResolveProfileFramework(environment, framework);" not in dispatcher:
    raise SystemExit("framework dispatcher must delegate to the unified profile resolver")
for storefront in (
    "Storefront::Steam",
    "Storefront::XboxMicrosoftStore",
    "Storefront::GOG",
    "Storefront::EpicGamesStore",
):
    if storefront in profile_framework_resolver or storefront in dispatcher:
        raise SystemExit(f"framework resolution must not branch on storefront: {storefront}")

post = native[native.index("void __fastcall HookPostInputEvent"):native.index("bool ResolveGameFramework")]
barrier_exchange = post.index("g_pauseBarrierObserved.exchange(false")
forward_press = post.rfind("Forward(input, event, force);", 0, barrier_exchange)
if forward_press < 0 or forward_press > barrier_exchange:
    raise SystemExit("PauseGame barrier may be consumed only after the outer vanilla press dispatch returns")
if 'TryEnterCleanPause("vanilla PauseGame barrier after Escape/Start press", true, false)' not in post:
    raise SystemExit("verified PauseGame barrier must accept Clean Pause on press when vanilla pauses there")
if '"vanilla PauseGame barrier after Escape/Start release", false, false' not in post:
    raise SystemExit("verified PauseGame barrier must also be consumed on the retail Start-release pause path")
for needle in (
    "pause physical press:",
    "pause press preparation complete; setupMs=%llu",
    "pause physical release: key=%u sincePressMs=%llu",
    "pressToPauseMs=%llu",
):
    if needle not in native:
        raise SystemExit(f"pause transition timing diagnostic missing: {needle}")
if "g_originalPauseGame(" not in native:
    raise SystemExit("missing vanilla PauseGame forwarding call")

# The only direct PauseGame call in production must be the trampoline forward inside the detour.
if native.count("g_originalPauseGame(") != 1:
    raise SystemExit("production must never synthesize its own PauseGame calls")

print("pause barrier contract passed")
