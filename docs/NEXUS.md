# Nexus Mods publication copy — KCD2 Clean Pause v0.3.0

Prepared for the stable v0.3.0 ASI release.

## Page metadata

**Name**

KCD2 Clean Pause

**Version**

0.3.0

**Category**

User Interface

**Summary**

Pause Kingdom Come: Deliverance II while keeping the current gameplay view, HUD and subtitles visible.

**Runtime-tested**

- Kingdom Come: Deliverance II 1.5.6 — Steam, `release_1_5-15693`.
- Kingdom Come: Deliverance II 1.5.6 — PC Xbox Store / Xbox app.

Steam was tested with keyboard Escape. Xbox / Microsoft Store was tested with the accepted keyboard/controller pause flow.

**Additional compatibility**

GOG and Epic Games Store 1.5.6 exact environment profiles are implemented from distribution-specific evidence, but this project has not completed Clean Pause-specific in-game smoke QA on those storefronts. Do not describe GOG/Epic as runtime-tested.

For an otherwise-unmatched build whose metadata still identifies the verified `release_1_5-<numeric id>` ABI family, the mod can attempt a conservative compatibility fallback. It resolves `gEnv` from unique executable anchor evidence, validates the live runtime before installing hooks, and deliberately avoids borrowing known-build framework roots or presentation quirks. Other ABI branches and ambiguous evidence fail closed.

## Description

KCD2 Clean Pause changes how the normal pause action is presented.

Pressing **Escape** or **Xbox Start** pauses the game through KCD2's own pause lifecycle, but keeps the current gameplay frame visible instead of immediately drawing the normal pause-menu surface. The HUD, dialogue subtitles and active NPC overhead subtitles remain visible, and the retained image stays sharp without the normal pause depth-of-field blur.

KCD2 remains the owner of the actual pause state. The mod does not implement a separate pause system.

### Controls

- **Escape / Xbox Start while playing:** enter Clean Pause.
- **Escape / Xbox Start while in Clean Pause:** reveal the normal KCD2 pause menu.
- **Xbox B while in Clean Pause:** reveal the normal KCD2 pause menu.
- Once the normal pause menu is visible, its controls work normally.

Xbox B intentionally reveals the normal pause menu rather than resuming directly from Clean Pause.

### What the mod preserves

- current gameplay frame;
- gameplay HUD visibility;
- dialogue subtitles;
- active NPC overhead subtitles;
- synchronized game/audio pause;
- sharp presentation without normal pause DoF blur;
- the ordinary KCD2 pause menu for settings, save, quit and normal resume behavior.

### v0.3.0 compatibility changes

v0.3.0 replaces the older cross-build assumptions with explicit runtime profiles:

- Steam 1.5.6 uses its exact PE/build identity, canonical `gEnv`, independent anchor validation and canonical `CCryAction` / `IGameFramework` root.
- Xbox / Microsoft Store 1.5.6 uses exact runtime roots captured from the retail binary instead of the previous writable-memory `gEnv` scan and historical `IGame[16]` framework path.
- Shared Clean Pause behavior is profile/capability-driven rather than storefront-branched.
- Unknown `release_1_5` builds may use only the conservative validated fallback described above.
- Unsupported future ABI branches remain fail-closed.

## Antivirus / Smart App Control notice

The v0.3.0 native ASI may be reported by heuristic/ML antivirus scanners. Current reported detections include:

- Microsoft Defender: `Program:Win32/Wacapew.C!ml`;
- Cynet: `Malicious (score: 100)`;
- Symantec: `ML.Attribute.HighConfidence`.

These detections are not, by themselves, proof that the file is malicious. The project is open source, releases are built by the public GitHub Actions workflow, third-party dependencies are pinned/verified, and the release publishes exact provenance/checksums.

Issue #38 tracks antivirus/security-product compatibility and reputation as non-blocking follow-up work. Vendor reclassification is not required for this stable release.

Use the exact hashes from the published GitHub Release `SHA256SUMS.txt` when verifying the downloaded asset.

## Installation

The v0.3.0 ASI package includes the pinned official x64 **Ultimate ASI Loader** used by the supported installation path.

### Fresh installation

1. Close Kingdom Come: Deliverance II.
2. Remove any old standalone Clean Pause `version.dll` installation.
3. Open the directory containing the game executable / `WHGame.dll`.
4. Copy both files from the package into that same directory:
   - `dinput8.dll`
   - `KCD2CleanPause.asi`
5. Start the game normally.

### Existing ASI loader

If another mod already installed a compatible `dinput8.dll`, **do not overwrite it blindly**.

`KCD2CleanPause.asi` must be placed where that existing loader actually searches for plugins. With Ultimate ASI Loader, the simplest shared-loader layout is to put `KCD2CleanPause.asi` beside the existing `dinput8.dll`. Ultimate ASI Loader can also load plugins from its `scripts/` and `plugins/` directories.

Do not install the ASI edition together with an old standalone Clean Pause `version.dll` edition.

## Known behavior

- Xbox B from Clean Pause reveals the ordinary pause menu rather than resuming directly.
- On Steam, a single residual visual frame can still be visible during Clean Pause entry. It is non-blocking and tracked in #52.

## Troubleshooting

When Clean Pause is loaded successfully, it writes `kcd2_clean_pause_native.log` beside `KCD2CleanPause.asi`.

If no log is created, verify that the ASI loader is actually loading the plugin from its configured search path.

If the game starts with the loader alone but fails after adding only `KCD2CleanPause.asi`, report:

- KCD2 version;
- storefront/build;
- locations of `dinput8.dll` and `KCD2CleanPause.asi`;
- whether the game starts with the loader present and Clean Pause removed;
- `kcd2_clean_pause_native.log`, if one was created.

The native log records build/profile identity, environment/framework locator strategy, runtime capabilities and hook installation.

## Uninstall

Close KCD2 and remove:

- `KCD2CleanPause.asi`;
- optional `kcd2_clean_pause_native.log`.

Remove `dinput8.dll` only if no other installed ASI mod needs that loader.

Native hooks are process-lifetime state; hot unload/reload is unsupported.

## Credits

- **ThirteenAG** — Ultimate ASI Loader, MIT License.
- **TsudaKageyu / MinHook contributors** — MinHook and bundled HDE components under their respective licenses.
- **Warhorse Studios** — Kingdom Come: Deliverance II.

Source code and issue tracker:
https://github.com/Vyachean/kcd2-clean-pause

## Permissions recommendation

Until the project adopts an explicit license for its own Clean Pause source, use conservative Nexus permissions for the author's original work:

- redistribution: permission required;
- modification/conversion: permission required;
- asset use in other mods: permission required;
- commercial use: not permitted without permission.

These permissions do not replace or restrict the separate licenses of bundled third-party components.

## Main file

**File name**

KCD2 Clean Pause v0.3.0 — ASI

**Version**

0.3.0

**Upload this artifact**

`kcd2-clean-pause-v0.3.0-asi.zip`

**File description**

Stable ASI release for KCD2 1.5.6. Runtime-tested on Steam and Xbox / Microsoft Store. Includes KCD2 Clean Pause, the pinned official x64 Ultimate ASI Loader for fresh installation, installation instructions, provenance/checksums and required third-party license notices.

Upload only the immutable GitHub Release artifact, not a local or CI rebuild. The standalone `version.dll` package remains CI-only under the current ASI-first publication policy.

## Changelog

### 0.3.0

- Adds the runtime-tested Steam 1.5.6 exact profile.
- Replaces Xbox legacy scanning/`IGame[16]` framework discovery with exact retail-captured runtime roots.
- Unifies build/profile/capability handling around one shared Clean Pause runtime.
- Adds a conservative compatibility fallback for otherwise-unmatched builds in the verified `release_1_5` ABI family.
- Removes the production translation-unit wrapper.
- Preserves HUD, dialogue subtitles, active NPC overhead subtitles and sharp pause presentation.
- Keeps KCD2 as the sole logical pause owner with fail-open vanilla-menu behavior.
- Documents known heuristic/ML antivirus detections and public build provenance.

## Nexus upload checklist — v0.3.0

- Upload only the immutable GitHub Release `kcd2-clean-pause-v0.3.0-asi.zip`.
- Set file version to **0.3.0**.
- Category: **User Interface**.
- Add relevant UI / Quality of Life tags if available.
- Apply any Nexus-required AI-generated-content disclosure/tag applicable to the project.
- Do not claim GOG/Epic as runtime-tested until their smoke QA is completed.
- Keep the antivirus notice factual and point to source/provenance/checksums.
- If Nexus quarantines the file, keep the immutable artifact and provide its GitHub release/provenance information to Nexus moderation rather than repeatedly rebuilding/reuploading.
- Confirm the archive contains no nested archive and the displayed Nexus file version is **0.3.0** before publishing.

## Optional presentation asset

For the mod-page image, prefer a real in-game screenshot taken while Clean Pause is active, ideally with dialogue subtitles visible. Do not use a generated mock gameplay screenshot as evidence of mod behavior.
