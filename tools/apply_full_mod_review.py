from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


native = ROOT / "native/src/clean_pause_native.cpp"
replace_once(
    native,
    '''struct HudVisibilitySnapshot {
    bool visible[kHudClipCount]{};
    bool captured{};
};
''',
    '''struct HudVisibilitySnapshot {
    bool visible[kHudClipCount]{};
    bool rootVisible{};
    bool captured{};
};
''',
    "snapshot root visibility field",
)
replace_once(
    native,
    '''    if (!ValidateObjectVtable(hud, {kUIElementGetMovieClipByNameSlot}))
        return false;
''',
    '''    if (!ValidateObjectVtable(hud, {
            kUIElementGetMovieClipByNameSlot,
            kUIElementIsVisibleSlot,
            kUIElementSetVisibleSlot }))
        return false;
''',
    "HUD accessor validation",
)
replace_once(
    native,
    '''    HudVisibilitySnapshot next{};
    for (std::size_t i = 0; i < kHudClipCount; ++i) {
''',
    '''    HudVisibilitySnapshot next{};
    const auto isRootVisible = VFunc<IsVisibleFn>(hud, kUIElementIsVisibleSlot);
    bool rootVisible{};
    __try {
        rootVisible = isRootVisible && isRootVisible(hud);
    } __except (EXCEPTION_EXECUTE_HANDLER) {
        return false;
    }
    next.rootVisible = rootVisible;

    for (std::size_t i = 0; i < kHudClipCount; ++i) {
''',
    "capture root visibility",
)
old_restore_root = '''    // hud@0 is only the container. RC7d proved its visibility does not control the
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
'''
new_restore_root = '''    // Root hud@0 visibility is independent from the 28 C_UIHudMask children
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
'''
replace_once(native, old_restore_root, new_restore_root, "exact root restore prelude")
replace_once(
    native,
    '''        if (!ok)
            return false;
    }

    if (label && std::strcmp(label, "gameplay") == 0) {
''',
    '''        if (!ok)
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
''',
    "exact root restore completion",
)
replace_once(
    native,
    '''    for (std::size_t i = 0; i < kHudClipCount; ++i)
        target.visible[i] = visible[i];
    target.captured = true;
    return true;
}
''',
    '''    if (!ValidateObjectVtable(g_hudElement, {kUIElementIsVisibleSlot}))
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
''',
    "internal root visibility",
)
replace_once(
    native,
    '''    HudVisibilitySnapshot vanillaState{};
    if (!CaptureVanillaHudFromInternalMask(vanillaState)) {
        FailOpenHudMaskTransaction(nullptr, "authoritative internal HUD state unavailable");
        return;
    }
''',
    '''    HudVisibilitySnapshot vanillaState{};
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
''',
    "transaction read-failure fallback",
)
insert_before_find = '''bool FindRuntimeEnvironment(HMODULE whGame, RuntimeEnvironment& result)
'''
fingerprint = '''void LogWhGameFingerprint(HMODULE whGame)
{
    const auto* base = reinterpret_cast<const std::uint8_t*>(whGame);
    if (!IsReadable(base, sizeof(IMAGE_DOS_HEADER))) {
        Log("WHGame fingerprint unavailable: unreadable DOS header");
        return;
    }

    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        Log("WHGame fingerprint unavailable: invalid DOS signature");
        return;
    }

    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    if (!IsReadable(nt, sizeof(*nt)) || nt->Signature != IMAGE_NT_SIGNATURE) {
        Log("WHGame fingerprint unavailable: invalid PE header");
        return;
    }

    Log(
        "WHGame fingerprint: TimeDateStamp=0x%08lx SizeOfImage=0x%08lx CheckSum=0x%08lx",
        static_cast<unsigned long>(nt->FileHeader.TimeDateStamp),
        static_cast<unsigned long>(nt->OptionalHeader.SizeOfImage),
        static_cast<unsigned long>(nt->OptionalHeader.CheckSum));
}

'''
replace_once(native, insert_before_find, fingerprint + insert_before_find, "WHGame fingerprint logger")
replace_once(
    native,
    '''    if (!whGame) {
        Log("WHGame.dll not found; Clean Pause disabled");
        return 0;
    }

    RuntimeEnvironment environment{};
''',
    '''    if (!whGame) {
        Log("WHGame.dll not found; Clean Pause disabled");
        return 0;
    }

    LogWhGameFingerprint(whGame);

    RuntimeEnvironment environment{};
''',
    "WHGame fingerprint call",
)

bubbles = ROOT / "native/src/clean_pause_bubbles.cpp"
replace_once(
    bubbles,
    '''BubbleReleaseFn g_originalBubbleRelease{};
void* g_bubbleReleaseTarget{};
''',
    '''BubbleReleaseFn g_originalBubbleRelease{};
void* g_bubbleReleaseTarget{};
std::atomic<void*> g_bubbleInterfaceObject{nullptr};
''',
    "bubble target identity",
)
replace_once(
    bubbles,
    '''void __fastcall HookBubbleUpdate(void* bubbles)
{
    if (g_pauseMenuVisible.load(std::memory_order_acquire))
        return;
    if (g_originalBubbleUpdate)
        g_originalBubbleUpdate(bubbles);
}

void __fastcall HookBubbleRelease(void* bubbles, std::uint32_t bubbleId)
{
    if (g_pauseMenuVisible.load(std::memory_order_acquire))
        return;
    if (g_originalBubbleRelease)
        g_originalBubbleRelease(bubbles, bubbleId);
}
''',
    '''void __fastcall HookBubbleUpdate(void* bubbles)
{
    // MinHook patches the shared class method body. Suppress only the concrete
    // I_UIHudBubbles object discovered from this hud@0 instance.
    const bool target = bubbles == g_bubbleInterfaceObject.load(std::memory_order_acquire);
    if (target && g_pauseMenuVisible.load(std::memory_order_acquire))
        return;
    if (g_originalBubbleUpdate)
        g_originalBubbleUpdate(bubbles);
}

void __fastcall HookBubbleRelease(void* bubbles, std::uint32_t bubbleId)
{
    const bool target = bubbles == g_bubbleInterfaceObject.load(std::memory_order_acquire);
    if (target && g_pauseMenuVisible.load(std::memory_order_acquire))
        return;
    if (g_originalBubbleRelease)
        g_originalBubbleRelease(bubbles, bubbleId);
}
''',
    "bubble instance-scoped detours",
)
replace_once(
    bubbles,
    '''    if (!InstallHook(
            menuSetVisibleTarget,
            reinterpret_cast<void*>(&HookMenuSetVisible),
            reinterpret_cast<void**>(&g_originalMenuSetVisible),
            g_menuSetVisibleTarget))
        return false;

    bool visible{};
''',
    '''    if (!InstallHook(
            menuSetVisibleTarget,
            reinterpret_cast<void*>(&HookMenuSetVisible),
            reinterpret_cast<void**>(&g_originalMenuSetVisible),
            g_menuSetVisibleTarget))
        return false;

    // Publish the exact object identity only after every required hook is installed.
    // Repeated discovery can safely retarget this to a recreated hud@0 instance while
    // the globally patched methods continue forwarding all unrelated objects.
    g_bubbleInterfaceObject.store(bubbleInterface, std::memory_order_release);

    bool visible{};
''',
    "bubble identity publication",
)

mask_header = ROOT / "native/src/clean_pause_hud_mask.h"
replace_once(
    mask_header,
    '''// No C_UIHudMask or movieclip pointer is retained by this API.
''',
    '''// The hook layer retains only validated C_UIHudMask/source-monitor identities for
// detour scoping; callers receive no borrowed object and no movieclip pointer is retained.
''',
    "HUD-mask ownership comment",
)

cmake = ROOT / "native/CMakeLists.txt"
replace_once(
    cmake,
    '''  GIT_TAG v1.3.4
''',
    '''  # MinHook v1.3.4, pinned to the immutable commit behind the release tag.
  GIT_TAG c3fcafdc10146beb5919319d0683e44e3c30d537
''',
    "MinHook immutable pin",
)

hud_test = ROOT / "tests/test_hud_mask_transaction_contract.py"
replace_once(
    hud_test,
    '''    def test_transaction_never_whole_snapshots_partial_flash_state(self):
''',
    '''    def test_snapshot_preserves_root_hud_visibility_exactly(self):
        snapshot = NATIVE[NATIVE.index('struct HudVisibilitySnapshot'):NATIVE.index('HudVisibilitySnapshot g_gameplayHudSnapshot')]
        self.assertIn('bool rootVisible{};', snapshot)
        capture = NATIVE[NATIVE.index('bool CaptureHudVisibilitySnapshot'):NATIVE.index('bool RestoreHudVisibilitySnapshot')]
        restore = NATIVE[NATIVE.index('bool RestoreHudVisibilitySnapshot'):NATIVE.index('bool ShouldPinGameplayHudPresentation')]
        internal = NATIVE[NATIVE.index('bool CaptureVanillaHudFromInternalMask'):NATIVE.index('bool RestoreVanillaHudPresentation')]
        self.assertIn('next.rootVisible = rootVisible;', capture)
        self.assertIn('target.rootVisible = rootVisible;', internal)
        self.assertIn('if (currentRootVisible && !snapshot.rootVisible)', restore)
        self.assertIn('if (!currentRootVisible && snapshot.rootVisible)', restore)

    def test_transaction_read_failure_uses_prior_complete_internal_fallback(self):
        reconcile = NATIVE[NATIVE.index('void ReconcileHudMaskMutation()'):NATIVE.index('void FailOpenHudMaintenance')]
        self.assertIn('const HudVisibilitySnapshot fallback = g_vanillaPauseHudSnapshot;', reconcile)
        self.assertIn('fallback.captured ? &fallback : nullptr', reconcile)

    def test_runtime_logs_whgame_fingerprint_for_future_abi_gating(self):
        self.assertIn('void LogWhGameFingerprint(HMODULE whGame)', NATIVE)
        self.assertIn('TimeDateStamp=0x%08lx SizeOfImage=0x%08lx CheckSum=0x%08lx', NATIVE)
        bootstrap = NATIVE[NATIVE.index('DWORD WINAPI BootstrapThread'):]
        self.assertIn('LogWhGameFingerprint(whGame);', bootstrap)

    def test_transaction_never_whole_snapshots_partial_flash_state(self):
''',
    "HUD root/fail-open/fingerprint tests",
)

bubble_test = ROOT / "tests/test_bubble_contract.py"
replace_once(
    bubble_test,
    '''    def test_menu_freeze_arms_before_vanilla_show_and_releases_after_hide(self):
''',
    '''    def test_global_bubble_method_hooks_are_scoped_to_discovered_instance(self):
        self.assertIn('std::atomic<void*> g_bubbleInterfaceObject{nullptr};', BUBBLES)
        update = BUBBLES[BUBBLES.index('void __fastcall HookBubbleUpdate'):BUBBLES.index('void __fastcall HookBubbleRelease')]
        release = BUBBLES[BUBBLES.index('void __fastcall HookBubbleRelease'):BUBBLES.index('void __fastcall HookMenuSetVisible')]
        self.assertIn('bubbles == g_bubbleInterfaceObject.load', update)
        self.assertIn('bubbles == g_bubbleInterfaceObject.load', release)
        ensure = BUBBLES[BUBBLES.index('bool EnsureHooks'):]
        self.assertLess(ensure.index('g_menuSetVisibleTarget'), ensure.index('g_bubbleInterfaceObject.store'))

    def test_menu_freeze_arms_before_vanilla_show_and_releases_after_hide(self):
''',
    "bubble instance-scope test",
)

validator = ROOT / "tools/validate_native_contract.py"
replace_once(
    validator,
    '''mask_header = (ROOT / "native/src/clean_pause_hud_mask.h").read_text(encoding="utf-8")
abi = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")
''',
    '''mask_header = (ROOT / "native/src/clean_pause_hud_mask.h").read_text(encoding="utf-8")
bubbles = (ROOT / "native/src/clean_pause_bubbles.cpp").read_text(encoding="utf-8")
abi = (ROOT / "native/src/kcd2_abi.h").read_text(encoding="utf-8")
''',
    "validator bubble source",
)
replace_once(
    validator,
    '''    if needle in native or needle in blur or needle in abi or needle in mask:
''',
    '''    if needle in native or needle in blur or needle in abi or needle in mask or needle in bubbles:
''',
    "validator forbidden bubble scope",
)
replace_once(
    validator,
    '''    "CLEAN_PAUSE_BUILD_ID",
)
''',
    '''    "CLEAN_PAUSE_BUILD_ID",
    "LogWhGameFingerprint",
)
''',
    "validator fingerprint runtime",
)
replace_once(
    validator,
    '''if "FailOpenHudMaskTransaction(nullptr" not in transaction or "FailOpenHudMaskTransaction(&vanillaState" not in transaction:
    raise SystemExit("HUD-mask transaction must fail open on internal-read or gameplay-replay failure")
''',
    '''if "fallback.captured ? &fallback : nullptr" not in transaction or "FailOpenHudMaskTransaction(&vanillaState" not in transaction:
    raise SystemExit("HUD-mask transaction must fail open with the best complete internal fallback")
''',
    "validator transaction fallback",
)
replace_once(
    validator,
    '''if "setVisible(clip, snapshot.visible[i])" not in restore:
    raise SystemExit("restore must replay captured visibility, not force all children visible")

menu = native[native.index("void __fastcall HookMenuRender"):native.index("bool EnsureMenuRenderHook")]
''',
    '''if "setVisible(clip, snapshot.visible[i])" not in restore:
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
''',
    "validator root and bubbles",
)

release = ROOT / ".github/workflows/release.yml"
replace_once(
    release,
    '''      - .github/workflows/release.yml
    tags: ["v*"]
''',
    '''      - .github/workflows/release.yml
      - THIRD_PARTY_NOTICES.txt
    tags: ["v*"]
''',
    "release push notice trigger",
)
replace_once(
    release,
    '''      - .github/workflows/release.yml
  workflow_dispatch:
''',
    '''      - .github/workflows/release.yml
      - THIRD_PARTY_NOTICES.txt
  workflow_dispatch:
''',
    "release PR notice trigger",
)
exports_old = '''          foreach ($name in @("GetFileVersionInfoW", "GetFileVersionInfoSizeW", "VerQueryValueW")) {
            if ($exports -notmatch [regex]::Escape($name)) { throw "version.dll proxy export missing: $name" }
          }
'''
exports_new = '''          $expectedExports = @(
            "GetFileVersionInfoA", "GetFileVersionInfoByHandle", "GetFileVersionInfoExA",
            "GetFileVersionInfoExW", "GetFileVersionInfoSizeA", "GetFileVersionInfoSizeExA",
            "GetFileVersionInfoSizeExW", "GetFileVersionInfoSizeW", "GetFileVersionInfoW",
            "VerFindFileA", "VerFindFileW", "VerInstallFileA", "VerInstallFileW",
            "VerLanguageNameA", "VerLanguageNameW", "VerQueryValueA", "VerQueryValueW"
          )
          foreach ($name in $expectedExports) {
            if ($exports -notmatch [regex]::Escape($name)) { throw "version.dll proxy export missing: $name" }
          }
'''
replace_once(release, exports_old, exports_new, "release all proxy exports")
replace_once(
    release,
    '''          Copy-Item native/INSTALL_ASI.txt release/asi/INSTALL.txt
          Copy-Item $versionDll release/version-dll/version.dll
          Copy-Item native/INSTALL_VERSION_DLL.txt release/version-dll/INSTALL.txt
''',
    '''          Copy-Item native/INSTALL_ASI.txt release/asi/INSTALL.txt
          Copy-Item THIRD_PARTY_NOTICES.txt release/asi/THIRD_PARTY_NOTICES.txt
          Copy-Item $versionDll release/version-dll/version.dll
          Copy-Item native/INSTALL_VERSION_DLL.txt release/version-dll/INSTALL.txt
          Copy-Item THIRD_PARTY_NOTICES.txt release/version-dll/THIRD_PARTY_NOTICES.txt
''',
    "release package notices",
)
replace_once(
    release,
    '''          [[ "$(unzip -Z1 "$ASI_ASSET" | sort)" == $'INSTALL.txt\\nKCD2CleanPause.asi' ]]
          [[ "$(unzip -Z1 "$VERSION_ASSET" | sort)" == $'INSTALL.txt\\nversion.dll' ]]
''',
    '''          [[ "$(unzip -Z1 "$ASI_ASSET" | sort)" == $'INSTALL.txt\\nKCD2CleanPause.asi\\nTHIRD_PARTY_NOTICES.txt' ]]
          [[ "$(unzip -Z1 "$VERSION_ASSET" | sort)" == $'INSTALL.txt\\nTHIRD_PARTY_NOTICES.txt\\nversion.dll' ]]
''',
    "release exact notice contents",
)

validate = ROOT / ".github/workflows/validate.yml"
replace_once(validate, exports_old, exports_new, "validate all proxy exports")

package_test = ROOT / "tests/test_dual_package_contract.py"
replace_once(
    package_test,
    '''RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
''',
    '''RELEASE = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
NOTICES = (ROOT / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
''',
    "package notice fixture",
)
replace_once(
    package_test,
    '''        self.assertIn("SHA256SUMS.txt", RELEASE)
''',
    '''        self.assertIn("SHA256SUMS.txt", RELEASE)
        self.assertGreaterEqual(RELEASE.count("THIRD_PARTY_NOTICES.txt"), 5)
        self.assertIn("MinHook v1.3.4", NOTICES)
        self.assertIn("Copyright (C) 2009-2017 Tsuda Kageyu.", NOTICES)
        self.assertIn("Redistributions in binary form must reproduce", NOTICES)
''',
    "package notice contract",
)
