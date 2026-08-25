from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
native = (ROOT / "native/src/clean_pause_native.cpp").read_text(encoding="utf-8")
blur = (ROOT / "native/src/clean_pause_blur.cpp").read_text(encoding="utf-8")
abi = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")

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
    "kGameFrameworkPauseGameSlot",
    "PauseGameFn",
    "System.GetCVarValue",
)
for needle in forbidden:
    if needle in native or needle in blur or needle in abi:
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
    "XiStart = 516",
    "XiA = 526",
    "XiB = 527",
)
for needle in required_abi:
    if needle not in abi:
        raise SystemExit(f"missing verified ABI contract: {needle}")

required_runtime = (
    'getElement(g_flashUI, "Menu@0")',
    'getElement(g_flashUI, "hud@0")',
    "HookMenuRender",
    "HookHudUpdate",
    "CaptureHudVisibilitySnapshot",
    "RestoreHudVisibilitySnapshot",
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
    "KCD2 Clean Pause v0.1.0 active",
)
for needle in required_runtime:
    if needle not in native:
        raise SystemExit(f"missing production runtime contract: {needle}")

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
restore = native[native.index("bool RestoreHudVisibilitySnapshot"):native.index("void FailOpenHudMaintenance")]
for block, label in ((capture, "capture"), (restore, "restore")):
    if "getMovieClip(hud, kHudClipNames[i], nullptr)" not in block:
        raise SystemExit(f"{label} does not acquire HUD children through GetMovieClip")
    if "Release" in block:
        raise SystemExit(f"{label} must not Release borrowed GetMovieClip results")
if "info[kFlashDisplayInfoVisibleOffset] != 0" not in capture:
    raise SystemExit("capture must preserve exact pre-transition visibility")
if "setVisible(clip, snapshot.visible[i])" not in restore:
    raise SystemExit("restore must replay captured visibility, not force all children visible")

menu = native[native.index("void __fastcall HookMenuRender"):native.index("bool EnsureMenuRenderHook")]
for needle in ("GetMovieClip", "RestoreHudVisibilitySnapshot", "SetVisible", "Release"):
    if needle in menu:
        raise SystemExit(f"Menu Render hook performs forbidden HUD lifecycle work: {needle}")
if "g_originalRender(element);" not in menu:
    raise SystemExit("Menu Render hook must forward all non-suppressed renders")

freeze = native[native.index("bool ShouldFreezeHudFunction"):native.index("bool __fastcall HookHudCallFunction")]
if freeze.count("std::strcmp(") != 2:
    raise SystemExit("subtitle freeze whitelist must contain exactly two comparisons")

enter = native[native.index("bool TryEnterCleanPause"):native.index("void HandleHiddenInput")]
if enter.index("if (!blur::Disable())") > enter.index("g_cleanHidden.store(true"):
    raise SystemExit("DoF must be disabled before Clean Pause render ownership begins")

hidden = native[native.index("void HandleHiddenInput"):native.index("void __fastcall HookPostInputEvent")]
b_start = hidden.index("if (key == KeyId::XiB)")
b_end = hidden.index("// Once a real Menu@0 render", b_start)
b_block = hidden[b_start:b_end]
if "Forward(input, event, force);" in b_block:
    raise SystemExit("physical B must not leak to gameplay/dialog/cutscene")
if "visible vanilla pause menu via B" not in b_block:
    raise SystemExit("v0.1.0 B contract must reveal the vanilla pause menu")
if b_block.index("RestoreBlurBestEffort") > b_block.index("g_cleanHidden.store(false"):
    raise SystemExit("B handoff must restore DoF before visible vanilla presentation")

print("stable native Clean Pause contract passed")
