# Nexus Mods publication copy — KCD2 Clean Pause v0.2.2

Prepared for the first Nexus Mods publication of the ASI edition.

## Page metadata

**Name**

KCD2 Clean Pause

**Version**

0.2.2

**Category**

User Interface

**Summary**

Pause Kingdom Come: Deliverance II without covering the current gameplay view, keeping the HUD and subtitles visible while the game is paused.

**Tested version**

Kingdom Come: Deliverance II 1.5.6 — PC Xbox Store / Xbox app version, tested with an Xbox controller.

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

1. Close Kingdom Come: Deliverance II.
2. Open the game directory containing the game executable / `WHGame.dll`.
3. If you do not already use an ASI loader, copy both:
   - `dinput8.dll`
   - `KCD2CleanPause.asi`
   into that directory.
4. If you already have a compatible `dinput8.dll` ASI loader installed, keep it and copy only `KCD2CleanPause.asi`.
5. Start the game normally.

Do not blindly overwrite an existing `dinput8.dll`. Multiple ASI plugins can share a compatible loader.

## Uninstall

Close the game and remove:

- `KCD2CleanPause.asi`
- optional `kcd2_clean_pause_native.log`

Remove `dinput8.dll` only if no other installed ASI mod needs it.

## Troubleshooting

The mod writes `kcd2_clean_pause_native.log` beside `KCD2CleanPause.asi`.

If Clean Pause does not activate or the game falls back to the normal pause menu, include that log when reporting the problem together with the game version and storefront/build you tested.

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

Do **not** upload the CI-only standalone `version.dll` package while issue #38 remains unresolved.

## Changelog

### 0.2.2

- Bundles the official x64 Ultimate ASI Loader for a complete fresh installation.
- Pins and verifies the upstream loader release and SHA-256 during packaging.
- Includes upstream loader provenance and MIT license.
- Keeps existing ASI-loader installations supported: users can retain their current `dinput8.dll` and install only `KCD2CleanPause.asi`.
- Clean Pause runtime behavior is unchanged from v0.2.1.

### 0.2.1 runtime changes included in this release

- Removes the pre-pause visual stall so picture/simulation and dialogue audio pause together.
- Prevents the hidden-HUD transition blink.
- Preserves dialogue subtitles and active NPC overhead subtitles.
- Keeps the retained frame sharp without pause DoF blur.
- Keeps KCD2 as the sole logical pause owner with a fail-open vanilla-menu fallback.

## Nexus upload checklist — 2026-08-27

- Upload only the GitHub Release `kcd2-clean-pause-v0.2.2-asi.zip`, not a local/CI rebuild.
- Category: **User Interface**.
- Add relevant UI / Quality of Life tags if available.
- Apply the required **AI-Generated Content** tag because generative AI was used for code development.
- Do not apply the **Nexus Mods Turns 25** event tag; the 2026 event rules prohibit generative-AI code/assets for participating mods.
- Keep the page hidden/unpublished until the uploaded file has completed Nexus security scanning.
- If the file is quarantined, do not delete/reupload it repeatedly; retain the file and provide the GitHub release/provenance information to Nexus moderation.
- Before pressing Publish, confirm the displayed Nexus file version is **0.2.2** and the archive contains no nested archives.

## Optional presentation asset

For the mod-page image, prefer a real in-game screenshot taken while Clean Pause is active, ideally with dialogue subtitles visible. Do not use a generated mock gameplay screenshot as evidence of mod behavior.
