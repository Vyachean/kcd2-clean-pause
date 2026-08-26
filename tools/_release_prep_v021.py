from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one guarded replacement, got {count}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


# Defensive runtime hardening: never publish a pause barrier if the MinHook
# trampoline is unexpectedly unavailable.
replace_once(
    "native/src/clean_pause_native.cpp",
    '''    // KCD2 remains the sole pause owner and receives the exact vanilla arguments.\n    if (g_originalPauseGame)\n        g_originalPauseGame(framework, pause, force, fadeOutInMs);\n\n    if (!observe || !g_pendingPauseAttempt.load(std::memory_order_acquire)) {\n''',
    '''    // KCD2 remains the sole pause owner and receives the exact vanilla arguments.\n    // If the trampoline is unexpectedly unavailable, fail open rather than publishing\n    // a barrier for a pause call that never reached vanilla.\n    if (!g_originalPauseGame) {\n        if (observe)\n            g_pauseTransitionActive.store(false, std::memory_order_release);\n        return;\n    }\n    g_originalPauseGame(framework, pause, force, fadeOutInMs);\n\n    if (!observe || !g_pendingPauseAttempt.load(std::memory_order_acquire)) {\n''',
)

replace_once(
    "tests/test_pause_barrier_contract.py",
    '''        self.assertIn("framework == g_gameFramework", hook)\n        self.assertIn("g_pendingPauseAttempt.load", hook)\n''',
    '''        self.assertIn("framework == g_gameFramework", hook)\n        self.assertIn("g_pendingPauseAttempt.load", hook)\n        self.assertIn("if (!g_originalPauseGame)", hook)\n''',
)

replace_once(
    "tools/validate_native_contract.py",
    '''if "g_pauseTransitionActive.store(true" not in pause_hook:\n    raise SystemExit("HUD transaction must arm only when the verified vanilla PauseGame call begins")\n''',
    '''if "g_pauseTransitionActive.store(true" not in pause_hook:\n    raise SystemExit("HUD transaction must arm only when the verified vanilla PauseGame call begins")\nif "if (!g_originalPauseGame)" not in pause_hook:\n    raise SystemExit("PauseGame observer must fail open if its vanilla trampoline is unavailable")\n''',
)

# v0.2.1 public release policy: build/validate both editions, but publish only
# the retail-accepted ASI asset while standalone Defender issue #38 is unresolved.
replace_once(
    ".github/workflows/release.yml",
    '''          $asiHash = (Get-FileHash "release/$asiAsset" -Algorithm SHA256).Hash.ToLowerInvariant()\n          $versionHash = (Get-FileHash "release/$versionAsset" -Algorithm SHA256).Hash.ToLowerInvariant()\n          @(\n            "$asiHash  $asiAsset",\n            "$versionHash  $versionAsset"\n          ) | Set-Content release/SHA256SUMS.txt -Encoding ascii\n''',
    '''          $asiHash = (Get-FileHash "release/$asiAsset" -Algorithm SHA256).Hash.ToLowerInvariant()\n          $versionHash = (Get-FileHash "release/$versionAsset" -Algorithm SHA256).Hash.ToLowerInvariant()\n          # Public checksums cover only assets we intentionally distribute. The standalone\n          # package is still built, packaged and hashed in CI while Defender issue #38 is open.\n          "$asiHash  $asiAsset" | Set-Content release/SHA256SUMS.txt -Encoding ascii\n          @(\n            "$asiHash  $asiAsset",\n            "$versionHash  $versionAsset"\n          ) | Set-Content release/CI_SHA256SUMS.txt -Encoding ascii\n''',
)
replace_once(
    ".github/workflows/release.yml",
    '''            release/${{ steps.package.outputs.version_asset }}\n            release/SHA256SUMS.txt\n''',
    '''            release/${{ steps.package.outputs.version_asset }}\n            release/SHA256SUMS.txt\n            release/CI_SHA256SUMS.txt\n''',
)
replace_once(
    ".github/workflows/release.yml",
    '''          sha256sum -c SHA256SUMS.txt\n          unzip -t "$ASI_ASSET"\n''',
    '''          sha256sum -c CI_SHA256SUMS.txt\n          sha256sum -c SHA256SUMS.txt\n          unzip -t "$ASI_ASSET"\n''',
)
replace_once(
    ".github/workflows/release.yml",
    '''          VERSION_ASSET: ${{ needs.build.outputs.version_asset }}\n          PRERELEASE: ${{ needs.build.outputs.prerelease }}\n''',
    '''          PRERELEASE: ${{ needs.build.outputs.prerelease }}\n''',
)
replace_once(
    ".github/workflows/release.yml",
    '''          args=("$TAG" "release/$ASI_ASSET" "release/$VERSION_ASSET" "release/SHA256SUMS.txt" --title "KCD2 Clean Pause $TAG" --notes-file docs/RELEASE_NOTES.md --verify-tag)\n''',
    '''          # Standalone version.dll is intentionally not a public v0.2.1 asset while #38 is unresolved.\n          args=("$TAG" "release/$ASI_ASSET" "release/SHA256SUMS.txt" --title "KCD2 Clean Pause $TAG" --notes-file docs/RELEASE_NOTES.md --verify-tag)\n''',
)

replace_once(
    "tests/test_dual_package_contract.py",
    '''    def test_release_publishes_two_mutually_exclusive_assets(self):\n        self.assertIn("KCD2CleanPause.asi", RELEASE)\n        self.assertIn("version.dll", RELEASE)\n        self.assertIn("-asi.zip", RELEASE)\n        self.assertIn("-version-dll.zip", RELEASE)\n        self.assertIn("INSTALL_ASI.txt", RELEASE)\n        self.assertIn("INSTALL_VERSION_DLL.txt", RELEASE)\n        self.assertIn("SHA256SUMS.txt", RELEASE)\n        self.assertGreaterEqual(RELEASE.count("THIRD_PARTY_NOTICES.txt"), 5)\n        self.assertIn("MinHook v1.3.4", NOTICES)\n        self.assertIn("Copyright (C) 2009-2017 Tsuda Kageyu.", NOTICES)\n        self.assertIn("Redistributions in binary form must reproduce", NOTICES)\n''',
    '''    def test_release_validates_both_editions_but_publishes_only_allowed_assets(self):\n        self.assertIn("KCD2CleanPause.asi", RELEASE)\n        self.assertIn("version.dll", RELEASE)\n        self.assertIn("-asi.zip", RELEASE)\n        self.assertIn("-version-dll.zip", RELEASE)\n        self.assertIn("INSTALL_ASI.txt", RELEASE)\n        self.assertIn("INSTALL_VERSION_DLL.txt", RELEASE)\n        self.assertIn("CI_SHA256SUMS.txt", RELEASE)\n        self.assertIn("SHA256SUMS.txt", RELEASE)\n        publish = RELEASE[RELEASE.index("- name: Publish GitHub Release") :]\n        self.assertIn('"release/$ASI_ASSET" "release/SHA256SUMS.txt"', publish)\n        self.assertNotIn("VERSION_ASSET", publish)\n        self.assertGreaterEqual(RELEASE.count("THIRD_PARTY_NOTICES.txt"), 5)\n        self.assertIn("MinHook v1.3.4", NOTICES)\n        self.assertIn("Copyright (C) 2009-2017 Tsuda Kageyu.", NOTICES)\n        self.assertIn("Redistributions in binary form must reproduce", NOTICES)\n''',
)

(ROOT / "VERSION").write_text("0.2.1\n", encoding="utf-8")

(ROOT / "CHANGELOG.md").write_text('''# Changelog

## Unreleased

No unreleased changes yet.

## v0.2.1 — 2026-08-26

Patch release for the retail-accepted no-blink Clean Pause transition on KCD2 1.5.6.

- Prevents KCD2's pause HUD-mask transition from rendering an intermediate hidden-HUD frame before Clean Pause presentation is established.
- Narrows HUD/subtitle presentation pinning to the actual validated vanilla `PauseGame` transition instead of the whole Start press/release correlation window, eliminating the pre-pause visual stall while keeping dialogue/audio pause synchronized with the retained frame.
- Uses KCD2's authoritative `C_UIHudMask` state for vanilla-menu handoff while keeping KCD2 as the sole logical pause/HUD owner.
- Scopes globally patched HUD-mask and NPC-bubble method hooks to the exact runtime objects discovered from the current `hud@0` instance.
- Preserves the root `hud@0` visibility state exactly, including configurations where `wh_ui_ShowHud` disables the whole HUD.
- Strengthens transactional fail-open behavior so an internal-state read failure restores the last complete vanilla HUD state instead of exposing a mixed presentation.
- Adds runtime `VERSION`, Git build id, and `WHGame.dll` PE fingerprint logging so retail evidence can be tied to a specific binary and future game-version compatibility gates.
- Pins MinHook v1.3.4 to its immutable commit and includes the required MinHook/HDE redistribution notice in binary packages.
- Expands validation to verify the complete 17-export standalone `version.dll` proxy surface.
- Promotes the ASI loading path used with the upstream Ultimate ASI Loader to the supported v0.2.1 distribution after retail acceptance.
- Withholds the v0.2.1 standalone `version.dll` asset while Microsoft Defender issue #38 remains unresolved; the standalone target continues to build and validate in CI but is not publicly distributed by this release.

## v0.2.0 — 2026-08-25

Stable feature release for the retail-proven standalone Clean Pause path.

- Consolidates the feature work previously published incrementally as `v0.1.1-rc.1` through `v0.1.1-rc.4`.
- Adds dual ASI / standalone `version.dll` distribution built from the same Clean Pause runtime.
- Adds process-wide duplicate-load protection.
- Keeps Clean Pause sharp by temporarily removing pause DoF blur and restoring the prior graphics state before normal vanilla presentation resumes.
- Preserves normal dialogue subtitles and active NPC overhead subtitles across the vanilla-owned pause transition.
- Keeps the accepted Start/Escape/B behavior and fail-open vanilla pause contract.
- Marks the standalone `version.dll` edition supported after retail acceptance of normal pause/menu/resume behavior.
- Keeps the ASI edition experimental until its loading path receives direct retail testing.

The old `v0.1.1-rc.1` through `v0.1.1-rc.4` tags remain immutable historical prereleases. No stable `v0.1.1` is planned.

## v0.1.1-rc.4 — 2026-08-25

Historical prerelease from before versioning normalization.

- Preserves active NPC speech bubbles / overhead subtitles across the vanilla pause transition instead of restoring only the root `Bubbles` HUD clip.
- Discovers KCD2's `C_UIHudBubbles` runtime object through the `hud@0` listener list and MSVC RTTI; no fixed `WHGame.dll` RVA is introduced.
- Freezes only `I_UIHudBubbles::UpdateBubbles()` and `ReleaseBubble()` while `Menu@0` is logically visible, arming before vanilla `SetVisible(true)` and releasing after `SetVisible(false)` returns.
- Keeps the bubble hook optional/fail-open so an unsupported listener layout cannot disable the proven Clean Pause path.
- Retains blur-free presentation, exact DoF restoration, dual ASI / standalone packaging, and duplicate-load protection.

## v0.1.1-rc.3 — 2026-08-25

Historical prerelease from before versioning normalization.

- Fixes the rc.2 Lua CVar getter from nonexistent `System.GetCVarValue` to CryEngine's actual `System.GetCVar` API.
- Retail-confirmed on the primary Xbox Store KCD2 1.5.6 target that Xbox Start enters Clean Pause again and the retained frame is sharp with the pause DoF blur removed.

## v0.1.1-rc.2 — 2026-08-25

Superseded historical prerelease. Do not use for testing.

- Attempted blur-free Clean Pause by temporarily disabling `wh_cl_NearDof` and `r_DepthOfField`.
- Used nonexistent Lua API `System.GetCVarValue`, causing the DoF capability path to fail open to the ordinary visible pause menu on retail.
- Added a process-wide guard so accidental simultaneous ASI + `version.dll` installation cannot install duplicate Clean Pause hooks.

## v0.1.1-rc.1 — 2026-08-25

Historical prerelease from before versioning normalization.

- Adds `KCD2CleanPause.asi`, loaded by a compatible shared ASI loader.
- Retains the standalone `version.dll` edition for self-contained installation.
- Builds both editions from the same runtime; only bootstrap/loading differs.

## v0.1.0 — 2026-08-24

Initial stable release.

- Uses KCD2's own pause lifecycle rather than a custom PauseGame implementation.
- Hides only the vanilla pause-menu render surface during Clean Pause.
- Preserves gameplay HUD child visibility, including tested subtitle presentation.
- Escape/Start reveals the existing vanilla pause menu.
- Xbox B from Clean Pause also reveals the vanilla pause menu; direct B resume is deferred.
- Removes experimental action-map, `only_ui`, Menu-visibility, synthetic B-replay, long-lived movieclip-pointer, and destructive movieclip-Release approaches from production.
- Targeted and retail-tested against KCD2 1.5.6, primarily the PC Xbox Store / Xbox app build.
''', encoding="utf-8")

(ROOT / "docs/RELEASE_NOTES.md").write_text('''# KCD2 Clean Pause v0.2.1

Stable patch release for **Kingdom Come: Deliverance II 1.5.6** on Windows.

## What changed

- Fixes the visible pause-entry discontinuity from v0.2.0: Clean Pause no longer performs HUD presentation work throughout the physical Start press/release interval.
- Arms HUD/subtitle preservation only around KCD2's verified vanilla `IGameFramework::PauseGame(true, ...)` call, so the retained frame and dialogue/audio pause together instead of producing a temporary frozen picture with continuing speech.
- Prevents the pause HUD-mask transition from flashing a hidden-HUD frame while preserving KCD2 as the sole logical pause owner.
- Uses KCD2's authoritative `C_UIHudMask` state for safe vanilla-menu handoff and fail-open recovery.
- Preserves exact root `hud@0` visibility and scopes shared MinHook detours to the exact runtime HUD-mask / bubble instances.
- Adds build identity and `WHGame.dll` fingerprint logging and strengthens packaging/license validation.

## Retail acceptance

The v0.2.1 ASI candidate was exercised on the primary Xbox Store / Xbox app KCD2 1.5.6 target with an Xbox controller and the upstream Ultimate ASI Loader. The accepted behavior includes:

- Start enters Clean Pause without the normal pause menu surface;
- picture/simulation and ongoing dialogue audio pause together immediately;
- gameplay HUD/subtitles remain retained without the previous transition blink;
- the retained frame remains sharp without pause DoF blur;
- second Start or Xbox B reveals the ordinary vanilla pause menu;
- normal menu resume returns to gameplay correctly.

Compatibility with arbitrary combinations of other ASI plugins is not claimed.

## Published package

- `kcd2-clean-pause-v0.2.1-asi.zip` — supported ASI edition; requires a compatible x64 ASI loader such as the upstream Ultimate ASI Loader `dinput8.dll` build.
- `SHA256SUMS.txt` — checksum for the published ASI package.

Do not intentionally install multiple Clean Pause editions at once.

## Standalone version.dll status

A v0.2.1 standalone `version.dll` is **not published**. Microsoft Defender flagged an earlier PR #34 standalone candidate as `Trojan:Win32/Wacatac.C!ml`; build provenance and static imports are consistent with a likely native-hooking false positive, but issue #38 remains unresolved. The standalone target continues to build and validate in CI, including all 17 proxy exports, but the project does not ask users to whitelist it and does not distribute the new standalone binary until that investigation is resolved.

The older v0.2.0 standalone release remains immutable history, but it does not contain the v0.2.1 pause-transition fix.

## Compatibility / safety

Runtime compatibility is claimed for KCD2 **1.5.6** only. KCD2 remains the sole pause owner; the mod observes the verified vanilla pause lifecycle and changes presentation only. Failure paths prefer an ordinary visible vanilla pause menu.
''', encoding="utf-8")

(ROOT / "README.md").write_text('''# KCD2 Clean Pause

Clean Pause for **Kingdom Come: Deliverance II** on Windows.

Tested target: **KCD2 1.5.6**, primarily the PC Xbox Store / Xbox app / Game Pass build with an Xbox controller.

## Release status

- **Current stable release:** `v0.2.1`.
- **Published v0.2.1 edition:** `KCD2CleanPause.asi`, retail-accepted with the upstream Ultimate ASI Loader.
- **Standalone `version.dll`:** the v0.2.1 target is intentionally withheld while Defender investigation #38 is unresolved. The last published standalone package is v0.2.0.

`v0.2.1` fixes the remaining pause-entry discontinuity: picture/simulation and ongoing dialogue audio now pause together, while the gameplay HUD/subtitles remain retained without the previous hidden-HUD transition blink.

Use the GitHub Releases page as the source of truth for versions and assets that are actually published.

## Behavior

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  Escape / Xbox Start -> visible vanilla pause menu
  Xbox B               -> visible vanilla pause menu

Vanilla pause menu
  normal KCD2 controls -> resume / settings / save / quit
```

Clean Pause uses KCD2's own pause lifecycle. The vanilla pause menu remains logically open, but its render surface is suppressed while the gameplay presentation is retained. The mod does not manufacture a second pause state.

The current release also removes the vanilla pause depth-of-field blur while Clean Pause is active and preserves normal dialogue subtitles plus active NPC overhead speech bubbles.

### Known behavior

Xbox **B does not resume directly from Clean Pause**. It reveals the ordinary KCD2 pause menu; use the normal menu controls to resume. This is the accepted product contract.

Compatibility is currently claimed for **KCD2 1.5.6 only**. A game update requires ABI revalidation before support is claimed.

## Editions

Both native targets compile the same runtime and remain mutually exclusive installations.

- **ASI edition — current supported v0.2.1 distribution:** `KCD2CleanPause.asi`; requires a compatible x64 ASI loader.
- **Standalone edition — built and validated, but v0.2.1 not distributed:** `version.dll`; public distribution is blocked by Defender investigation #38.

Do **not** intentionally install both Clean Pause editions at the same time. A process-wide guard prevents duplicate hooks if both are accidentally loaded, but dual installation is unsupported.

See [Dual native packages](docs/DUAL_PACKAGE.md) for the package contract.

## Install — ASI edition

1. Close KCD2.
2. Remove any standalone Clean Pause `version.dll` installation.
3. Install a compatible x64 ASI loader for KCD2, normally the upstream Ultimate ASI Loader `dinput8.dll` beside the KCD2 executable / `WHGame.dll`.
4. Copy `KCD2CleanPause.asi` from the `-asi.zip` release asset beside the loader.
5. Start the game normally.

Do not overwrite an existing `dinput8.dll` blindly. Multiple ASI plugins may share one compatible loader, but universal coexistence with every native plugin is not claimed.

## Standalone version.dll edition

The project still builds and validates the standalone proxy, but **v0.2.1 does not publish a standalone asset** while #38 is unresolved. Do not obtain or whitelist an unofficial v0.2.1 `version.dll` build to work around that release gate.

The immutable v0.2.0 release still contains the older retail-proven standalone package, but it does not include the v0.2.1 transition fix.

Both native editions write `kcd2_clean_pause_native.log` beside their own module.

## Uninstall

Close KCD2 and remove `KCD2CleanPause.asi` plus the optional `kcd2_clean_pause_native.log`. Remove the ASI loader `dinput8.dll` only if no other installed mod needs it.

## Architecture

The production architecture deliberately keeps KCD2 as the sole pause owner:

- the physical Escape/Start event is forwarded to KCD2;
- a validated `IGameFramework::PauseGame(true, ...)` hook observes the real vanilla pause transition but never synthesizes a pause and forwards the original arguments unchanged;
- pending Start/release correlation alone performs no HUD replay;
- HUD/subtitle preservation is armed only for the real vanilla pause transition;
- `Menu@0` remains logically visible while only its `Render()` is suppressed during Clean Pause;
- authoritative `C_UIHudMask` visibility is retained for safe vanilla-menu handoff/fail-open;
- exact root HUD visibility, dialogue subtitles, NPC overhead subtitles and DoF state are preserved;
- unresolved core state fails open to the visible vanilla pause menu.

No action-map replacement, fixed storefront-specific `WHGame.dll` RVA, replacement overlay, long-lived movieclip pointer, destructive borrowed-handle release, or synthetic B-resume replay is used.

See [Design](docs/DESIGN.md) for the complete production architecture.

## Versioning

The project follows SemVer and immutable tag-backed GitHub releases. Feature releases bump MINOR, fixes bump PATCH, and release candidates are used only when the supported release itself still needs acceptance. See [Release process](docs/RELEASE.md).

## Documentation

Start with the [documentation index](docs/README.md).

Key current documents:

- [Current status and release readiness](docs/STATUS_AND_PLAN.md)
- [Design](docs/DESIGN.md)
- [Testing](docs/TESTING.md)
- [Release process](docs/RELEASE.md)
''', encoding="utf-8")

(ROOT / "docs/STATUS_AND_PLAN.md").write_text('''# Current status and plan

## Release status

**v0.2.1** is the current stable release target for KCD2 1.5.6 Windows retail.

Support/distribution status is per edition:

- **`KCD2CleanPause.asi`: supported / retail-accepted** on the primary PC Xbox Store / Xbox app target using the upstream Ultimate ASI Loader;
- **standalone `version.dll`: built and validated but v0.2.1 distribution withheld** while Defender investigation #38 is unresolved. The last published standalone package remains v0.2.0.

## v0.2.1 acceptance

The accepted retail behavior is:

- Xbox Start enters the vanilla-owned Clean Pause without drawing the normal pause menu;
- simulation/picture and ongoing dialogue audio pause together immediately;
- main HUD and dialogue subtitles remain retained without the previous hide/restore blink;
- the retained frame is sharp without vanilla pause DoF blur;
- active NPC overhead subtitles remain preserved;
- second Start or B reveals the already-open vanilla pause menu;
- closing the menu and resuming returns to normal gameplay.

The transition fix is implemented by restricting HUD/subtitle presentation ownership to KCD2's actual validated `IGameFramework::PauseGame(true, ...)` transition. Pending Start/release correlation by itself performs no Flash replay.

## Product contract

```text
Running
  Escape / Xbox Start -> Clean Pause

Clean Pause
  sharp retained frame, no pause DoF blur
  visible dialogue subtitles remain visible
  active NPC overhead subtitles remain visible
  Escape / Xbox Start -> visible vanilla pause menu
  Xbox B               -> visible vanilla pause menu
```

Direct `Clean Pause -> B -> Running` is not part of the current contract.

## Accepted runtime architecture

1. KCD2 is the sole pause owner.
2. Physical Escape/Start input is forwarded to KCD2.
3. The verified target `IGameFramework::PauseGame(true, ...)` call is the preferred transition barrier; all vanilla arguments are forwarded unchanged.
4. Pending input correlation alone does not pin HUD/subtitle presentation.
5. `Menu@0` remains logically visible; only `Menu@0::Render()` is suppressed during Clean Pause.
6. Gameplay presentation snapshots preserve exact root `hud@0` visibility plus the 28 HUD-child visibility booleans.
7. The no-blink transaction reads authoritative vanilla child visibility from `I_UIHudMask::IsElementVisible` and never reconstructs complete vanilla state from a partial Flash mutation.
8. Global HUD-mask/bubble method detours are scoped to exact discovered runtime instances.
9. `IUIElement::GetMovieClip()` results are borrowed/call-local and never retained or released by the mod.
10. Subtitle-clearing Flash calls are narrowly suppressed only during the actual transition / active Clean Pause.
11. `wh_cl_NearDof` and `r_DepthOfField` are restored before visible vanilla presentation.
12. Unresolved core state fails open to visible vanilla pause.

## Release model

Both ASI and standalone targets are built and validated from the same runtime. Public assets are edition-gated: an edition with an unresolved safety/distribution blocker may remain a CI-only validated artifact while another retail-accepted edition is released.

For v0.2.1, only the ASI ZIP and its public checksum are attached to the GitHub Release. The standalone ZIP remains inside CI validation only until #38 is resolved.

## Remaining work

Blocking standalone v0.2.1 distribution:

- resolve Defender issue #38 and record an independent/Microsoft false-positive verdict before publishing a new `version.dll` asset.

Compatibility debt:

- strict `WHGame.dll` fingerprint enforcement remains tracked in #36;
- revalidate ABI facts on any KCD2 update from 1.5.6.

Non-blocking follow-up:

- verify coexistence with additional real KCD2 ASI plugins; current support is for the tested loader/runtime path, not universal plugin combinations;
- investigate safe direct B resume only if a canonical vanilla mechanism is found;
- broader cutscene/dialogue and repeated-cycle/load-transition robustness;
- process-lifetime hook/hot-unload policy remains tracked separately.

## Decision rule

> Reuse vanilla KCD2 pause ownership, scope presentation changes to the real pause transition, and prefer a visible vanilla-menu fallback over unverified state manipulation.
''', encoding="utf-8")

(ROOT / "docs/RELEASE.md").write_text('''# Release pipeline

GitHub Releases are the canonical public distribution channel. Generated native binaries/ZIP files are not committed.

## Versioning policy

The project follows Semantic Versioning with immutable tag-backed releases.

- Stable releases use `vMAJOR.MINOR.PATCH`.
- Prereleases use `vMAJOR.MINOR.PATCH-rc.N` (or `alpha` / `beta` where appropriate).
- Before 1.0, backward-compatible features increment MINOR; backward-compatible fixes increment PATCH.
- Published tags/releases are immutable and are never moved or recycled.

## Production source

Both native editions compile the same Clean Pause runtime. Edition-specific bootstrap files are `native/src/asi_entry.cpp` and `native/src/version_proxy.cpp` / `native/src/version.def`.

## Pull-request and main-branch gates

Release-affecting changes must pass:

1. repository Python tests;
2. `tools/validate_native_contract.py`;
3. x64 MSVC builds of both native targets;
4. complete standalone proxy-export validation;
5. x64/static-runtime checks for both images;
6. release-shaped ZIP construction and integrity checks.

A PR never publishes a GitHub Release. A release-preparation merge to `main` with a new `VERSION` reruns the same gates, creates the immutable matching tag if absent, and publishes only the edition assets currently approved for public distribution.

## Preparing a release

1. Choose the next SemVer version.
2. Set `VERSION`.
3. Move `CHANGELOG.md` entries from `Unreleased` to the target version.
4. Update `docs/RELEASE_NOTES.md` and current support/distribution documentation.
5. Merge only after release-shaped CI is green.
6. The successful main workflow creates the matching immutable tag and GitHub Release automatically.

## Edition-gated publication

Build validation and public distribution are separate concerns. Both native targets remain continuously built so shared-runtime and proxy regressions are caught even if one edition has a temporary distribution blocker.

For **v0.2.1**:

- `KCD2CleanPause.asi` is the retail-accepted public edition;
- `version.dll` is still built, packaged and verified in Actions CI but is not attached to the public release while Defender investigation #38 remains unresolved;
- `SHA256SUMS.txt` covers only public release assets;
- `CI_SHA256SUMS.txt` covers both internally validated ZIPs and remains an Actions artifact rather than a public release asset.

When #38 is resolved, standalone publication can be restored in a later release without changing the shared runtime architecture.

## Publication flow

For an unpublished version on a qualifying main push, `.github/workflows/release.yml`:

1. validates `VERSION`;
2. reruns tests/native contract validation;
3. builds both x64 editions;
4. validates the complete 17-export standalone proxy surface and both PE/runtime properties;
5. constructs both edition ZIPs for CI validation;
6. writes internal checksums for both and public checksums for approved assets;
7. downloads and re-verifies all CI packages before publication;
8. creates the immutable matching tag on the exact workflow commit if absent;
9. creates the GitHub Release with only approved public assets and `--verify-tag`.

## Current edition policy

The ASI and standalone editions are mutually exclusive installations of the same runtime.

- **v0.2.1 ASI:** supported on the retail-tested KCD2 1.5.6 + upstream Ultimate ASI Loader path.
- **v0.2.1 standalone:** not publicly distributed until #38 is resolved.
- **v0.2.0 standalone:** remains immutable historical release and was retail-proven for that version, but does not include the v0.2.1 transition fix.

Support does not imply universal coexistence with every other native plugin.

## Version support

Runtime compatibility is pinned to KCD2 **1.5.6** ABI facts. A future game update requires revalidation before support is claimed.
''', encoding="utf-8")

(ROOT / "docs/DUAL_PACKAGE.md").write_text('''# Dual native packages

KCD2 Clean Pause builds the same native runtime in two mutually exclusive editions.

## ASI edition

```text
kcd2-clean-pause-v<VERSION>-asi.zip
  KCD2CleanPause.asi
  INSTALL.txt
  THIRD_PARTY_NOTICES.txt
```

Requires a compatible x64 ASI loader, normally installed as `dinput8.dll` beside the KCD2 executable / `WHGame.dll`.

## Standalone version.dll edition

```text
kcd2-clean-pause-v<VERSION>-version-dll.zip
  version.dll
  INSTALL.txt
  THIRD_PARTY_NOTICES.txt
```

The standalone target includes the Windows `version.dll` proxy and requires no separate ASI loader.

## Runtime identity

Both targets compile the same runtime source set; only bootstrap/loading differs. A process-wide guard prevents accidental duplicate hook installation, but intentional dual installation is unsupported.

## Build vs publication contract

CI always builds and validates **both** editions:

- both images must exist, target x64 and avoid dynamic MSVC runtime dependencies;
- standalone must export the complete required 17-function Windows version API surface;
- each ZIP must contain the expected binary, install text and third-party notices;
- internal Actions checksums cover both packages.

Public release assets are edition-gated. For **v0.2.1**, only the ASI ZIP is published because Defender investigation #38 blocks distribution of the new standalone binary. The standalone ZIP remains a CI-only validation artifact until that issue is resolved.

Do not obtain/whitelist an unofficial standalone build to bypass that gate.
''', encoding="utf-8")

(ROOT / "docs/ASI_RETAIL_ACCEPTANCE.md").write_text('''# ASI retail acceptance

> **Status for v0.2.1:** core ASI loader/runtime path accepted on KCD2 1.5.6 Xbox Store / Xbox app using the upstream Ultimate ASI Loader. Broader coexistence with arbitrary native plugins remains a non-blocking follow-up.

## Accepted installation baseline

- one compatible x64 Ultimate ASI Loader build as `dinput8.dll` beside the game executable / `WHGame.dll`;
- `KCD2CleanPause.asi` beside that loader;
- no Clean Pause standalone `version.dll` loaded at the same time.

## Retail evidence

Cumulative v0.2.1 candidate testing confirmed the ASI module loads and the native runtime is active. The final transition-scoped candidate confirms:

- Xbox Start enters Clean Pause;
- world simulation and ongoing dialogue audio pause together immediately;
- retained HUD/dialogue subtitles no longer show the previous hide/restore transition;
- normal pause DoF is absent from the retained Clean Pause frame;
- second Start or Xbox B reveals the vanilla pause menu;
- normal menu resume returns to gameplay.

This is sufficient for the tested ASI loading path to be the supported v0.2.1 distribution. It does not establish universal compatibility with every ASI plugin or loader fork.

## Coexistence follow-up

Repeat the core checks with representative real KCD2 ASI plugins sharing the same loader. Any conflict found there should be treated as plugin-coexistence compatibility debt rather than retroactively invalidating the already-tested single-loader/single-plugin path.
''', encoding="utf-8")

Path(__file__).unlink()
print("v0.2.1 release preparation applied")
