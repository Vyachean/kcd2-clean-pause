# Nexus Mods publication copy — KCD2 Clean Pause v0.2.2

Prepared for the currently published ASI edition.

> Release-candidate note: v0.2.2 remains the immutable Xbox / Microsoft Store-tested Nexus/stable release. GitHub prerelease v0.3.0-rc.1 contains fail-closed KCD2 1.5.6 profiles for Steam, GOG, Epic Games Store and Xbox / Microsoft Store. Do not promote the Nexus compatibility claim until the intended in-game smoke QA is complete and stable v0.3.0 is published.

## Page metadata

**Name**

KCD2 Clean Pause

**Version**

0.2.2

**Category**

User Interface

**Summary**

Pause Kingdom Come: Deliverance II without covering the current gameplay view, keeping the HUD and subtitles visible while the game is paused.

**Runtime-tested version for v0.2.2**

Kingdom Come: Deliverance II 1.5.6 — PC Xbox Store / Xbox app version, tested with an Xbox controller.

**Other storefronts**

GitHub prerelease v0.3.0-rc.1 contains explicit 1.5.6 compatibility profiles for Steam, GOG and Epic Games Store backed by public reverse-engineering/runtime evidence and automated Windows validation. Steam is the current Clean Pause smoke-test target; GOG/Epic should not yet be described as Clean Pause runtime-tested by this project.

## Description

KCD2 Clean Pause changes how the normal pause action is presented.

Pressing Escape or Xbox Start pauses the game through KCD2's own pause lifecycle, but keeps the current gameplay frame visible instead of immediately drawing the normal pause-menu surface. The HUD, dialogue subtitles, and active NPC overhead subtitles remain visible, and the retained image stays sharp without the normal pause depth-of-field blur.

### Controls

- **Escape / Xbox Start while playing:** enter Clean Pause.
- **Escape / Xbox Start while in Clean Pause:** reveal the normal KCD2 pause menu.
- **Xbox B while in Clean Pause:** reveal the normal KCD2 pause menu.
- Once the normal pause menu is visible, its controls work normally.

Xbox B intentionally reveals the normal pause menu rather than resuming directly from Clean Pause.

### What the mod preserves

- the current gameplay frame;
- gameplay HUD visibility;
- dialogue subtitles;
- active NPC overhead subtitles;
- synchronized game/audio pause;
- sharp presentation without the normal pause DoF blur;
- the ordinary KCD2 pause menu for settings, save, quit, and normal resume behavior.

Clean Pause does not create a separate pause system. KCD2 remains the owner of the actual pause state; the mod changes presentation around the verified vanilla pause transition and falls back to the visible vanilla menu if required state cannot be resolved safely.

## Installation

The main v0.2.2 package includes the official x64 **Ultimate ASI Loader** used by the tested setup.

### Fresh installation

1. Close Kingdom Come: Deliverance II.
2. Open the directory containing the game executable / `WHGame.dll`.
3. Copy both files from the package into that same directory:
   - `dinput8.dll`
   - `KCD2CleanPause.asi`
4. Start the game normally.

### Existing ASI loader

If another mod already installed a compatible `dinput8.dll`, **do not overwrite it blindly**.

`KCD2CleanPause.asi` must be placed where that existing ASI loader actually searches for plugins. With Ultimate ASI Loader, the simplest shared-loader layout is to put `KCD2CleanPause.asi` beside the existing `dinput8.dll`. Ultimate ASI Loader can also load plugins from its `scripts/` and `plugins/` directories.

Do not leave `dinput8.dll` in one directory and put `KCD2CleanPause.asi` beside `WHGame.dll` in another directory unless the existing loader is explicitly configured to scan that location.

Multiple ASI plugins can share one compatible loader, but the loader location and plugin search paths still matter.

## Uninstall

Close the game and remove:

- `KCD2CleanPause.asi`
- optional `kcd2_clean_pause_native.log`

Remove `dinput8.dll` only if no other installed ASI mod needs it.

## Troubleshooting

When Clean Pause is successfully loaded, it writes `kcd2_clean_pause_native.log` beside `KCD2CleanPause.asi`.

### No native log is created

If `kcd2_clean_pause_native.log` is not created at all, first verify that the ASI loader is actually loading `KCD2CleanPause.asi` from its configured plugin location. An ASI file placed beside `WHGame.dll` is not automatically discovered by a loader located elsewhere.

### Game crashes while loading native mods

Isolate the loader from Clean Pause:

1. Keep the ASI loader in the location being tested.
2. Temporarily remove `KCD2CleanPause.asi` and any other `.asi` files from that loader's search path.
3. Start the game.
4. If the game starts normally, add only `KCD2CleanPause.asi` and test again.

If the game works with the loader alone but crashes after adding Clean Pause, report it as a Clean Pause compatibility issue and include:

- game version;
- storefront/build — Steam, GOG, Epic Games Store, Xbox Store / Xbox app, or another build;
- location of `dinput8.dll`;
- location of `KCD2CleanPause.asi`;
- whether the game starts with the loader present and Clean Pause removed;
- `kcd2_clean_pause_native.log`, if one was created before the crash.

For v0.3.0-rc.1, the native log records the detected fingerprint/storefront/build profile and whether the fail-closed runtime gates reached hook installation.

Do not install the ASI edition together with an old standalone Clean Pause `version.dll` edition.

## Credits

- **ThirteenAG** — Ultimate ASI Loader, distributed under the MIT License. The release ZIP contains the exact upstream version/provenance and license text.
- **TsudaKageyu / MinHook contributors** — MinHook native hooking library and bundled HDE components under their respective licenses.
- **Warhorse Studios** — Kingdom Come: Deliverance II.

Source code and issue tracker:
https://github.com/Vyachean/kcd2-clean-pause

## Permissions recommendation

Until the project adopts an explicit license for its own Clean Pause source, use conservative Nexus permissions for the author's original work:

- redistribution: permission required;
- modification/conversion: permission required;
- asset use in other mods: permission required;
- commercial use: not permitted without permission.

These permissions do not replace or restrict the separate licenses of bundled third-party components such as Ultimate ASI Loader and MinHook.

## Main file

**File name**

KCD2 Clean Pause v0.2.2 — ASI

**Version**

0.2.2

**Upload this artifact**

`kcd2-clean-pause-v0.2.2-asi.zip`

**File description**

Main ASI release. Includes KCD2 Clean Pause, the pinned official x64 Ultimate ASI Loader for fresh installation, installation instructions, provenance/hashes, and required third-party license notices.

Do **not** upload a CI/development build as v0.2.2 and do **not** upload the CI-only standalone `version.dll` package while issue #38 remains unresolved.

## Changelog

### 0.2.2

- Bundles the official x64 Ultimate ASI Loader for a complete fresh installation.
- Pins and verifies the upstream loader release and SHA-256 during packaging.
- Includes upstream loader provenance and MIT license.
- Supports shared compatible ASI loaders, with the plugin installed in that loader's actual plugin search path.
- Clean Pause runtime behavior is unchanged from v0.2.1.

### 0.2.1 runtime changes included in this release

- Removes the pre-pause visual stall so picture/simulation and dialogue audio pause together.
- Prevents the hidden-HUD transition blink.
- Preserves dialogue subtitles and active NPC overhead subtitles.
- Keeps the retained frame sharp without pause DoF blur.
- Keeps KCD2 as the sole logical pause owner with a fail-open vanilla-menu fallback.

## Nexus upload checklist — v0.2.2 historical release

- Upload only the immutable GitHub Release `kcd2-clean-pause-v0.2.2-asi.zip`, not a local/CI rebuild.
- Category: **User Interface**.
- Add relevant UI / Quality of Life tags if available.
- Apply the required **AI-Generated Content** tag because generative AI was used for code development.
- Do not apply the **Nexus Mods Turns 25** event tag; the 2026 event rules prohibit generative-AI code/assets for participating mods.
- Keep the page hidden/unpublished until the uploaded file has completed Nexus security scanning.
- If the file is quarantined, do not delete/reupload it repeatedly; retain the file and provide the GitHub release/provenance information to Nexus moderation.
- Before pressing Publish, confirm the displayed Nexus file version is **0.2.2** and the archive contains no nested archives.

## Next-release compatibility checklist

Before changing the Nexus compatibility claim for Steam/GOG/Epic:

- test the published GitHub prerelease v0.3.0-rc.1 rather than an earlier diagnostic/CI build;
- complete the intended Clean Pause in-game smoke QA for every storefront being claimed as runtime-tested;
- if the Steam RC is accepted, publish stable v0.3.0 through the normal immutable GitHub release workflow;
- update the Nexus page version/changelog and tested-storefront wording together;
- upload only the stable v0.3.0 GitHub ASI artifact, not the RC artifact;
- retain fail-closed wording for unknown/mismatched KCD2 builds.

## Optional presentation asset

For the mod-page image, prefer a real in-game screenshot taken while Clean Pause is active, ideally with dialogue subtitles visible. Do not use a generated mock gameplay screenshot as evidence of mod behavior.
