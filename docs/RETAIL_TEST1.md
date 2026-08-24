# Xbox Store 1.5.6 retail candidate history

This note records the exact retail profile provenance and the first prerelease test result.

## Original retail source

The target `Libs/Config/defaultProfile.xml` was extracted from the Xbox Store / Xbox app KCD2 1.5.6 installation.

Original retail profile SHA-256:

```text
69ad9fd618cd31961fef8eb061f3f2723997df5e0fb257ec74d0d5f555592565
```

Confirmed properties:

```text
profile version="0"
open_menu/open_menu             -> keyboard="_keybinds_ref_", xboxpad="xi_start"
open_pause_menu/open_pause_menu -> keyboard="_keybinds_ref_", xboxpad="xi_start"
overlays priority               -> 12
```

The exact profile contains no `actionPass` filters. It does contain the retail `no_menu` actionFail filter for `open_menu`.

## v0.1.0-rc.1 — failed

Retail result on the target installation:

- Escape did not pause;
- Xbox Start did not pause;
- Clean Pause did not activate.

The rc1 profile had converted the two original pause actions to `consoleCmd="1"`. KCD2 keybind actions use the exact case-sensitive spelling `consoleCMD="1"`.

Because rc1 also removed the normal vanilla activation route, the command failure left both controls with no working pause action. rc1 is therefore invalid and must not be used for further acceptance testing.

rc1 patched-profile SHA-256:

```text
28e210454d749869b1fa26d4414ba3c055157e731856f9610d6ffce5ddfbc373
```

## v0.1.0-rc.2 source — fail-safe redesign

The next candidate is regenerated from the same verified original retail profile.

Current patched-profile SHA-256:

```text
9838db3747f7f36e0c9c281b8770bc7300998515407515b65493b8e9a9bcd14e
```

Versioned release source:

```text
vendor/kcd2/xbox-1.5.6/defaultProfile.clean-pause.xml.gz.b64
```

The new contract is:

```text
Escape / Start press
  -> clean_pause_enter_gameplay or clean_pause_enter_pause_context
  -> exact consoleCMD="1"

Escape / Start release
  -> original open_menu / open_pause_menu vanilla action
```

After successful custom entry, the exclusive `clean_pause_controls` map contains a release sink and consumes the same physical release. If the custom command does not execute, that map never becomes active and the original release-only action opens the vanilla pause menu.

The `no_menu` actionFail filter is mirrored to `clean_pause_enter_gameplay`, preventing the custom press route from bypassing vanilla restrictions.

## Packaging

Generated `.pak` and install `.zip` files are not tracked in Git.

Canonical release builder:

```text
tools/build_release.py
```

PR CI validates both the development builder and the self-contained release source. A release PR changes `VERSION`; after it reaches `main`, `.github/workflows/release.yml` publishes the matching GitHub tag/release and attaches the install ZIP plus `SHA256SUMS.txt`.

## rc2 runtime acceptance

The next test must establish, in this order:

1. Escape and Xbox Start are no longer dead controls;
2. successful custom entry happens on press and the same release is consumed;
3. if custom entry still fails, vanilla pause opens on release;
4. Clean Pause keeps the frame/subtitle unobscured;
5. B resumes without underlying dialogue/cutscene side effects;
6. second Escape/Start opens the real vanilla pause menu;
7. dialogue/cutscene audio and scripted progression resume coherently.

See `docs/TESTING.md` for the full matrix.
