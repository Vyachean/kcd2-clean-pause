# Release pipeline

GitHub Releases are the canonical public distribution channel. Generated native binaries/ZIP files are not committed.

## Versioning policy

The project follows Semantic Versioning with immutable tag-backed releases.

- Stable releases use `vMAJOR.MINOR.PATCH`.
- Prereleases use `vMAJOR.MINOR.PATCH-rc.N` (or `alpha` / `beta` where appropriate).
- Before 1.0, backward-compatible features increment **MINOR**; backward-compatible fixes increment **PATCH**.
- A release candidate number increments only when another candidate for the same target release is needed. It is not incremented for every merged PR.
- Published tags/releases are immutable and are never moved or recycled.

## Production source

Both native editions compile the same Clean Pause runtime. Edition-specific bootstrap files are `native/src/asi_entry.cpp` and `native/src/version_proxy.cpp` / `native/src/version.def`.

## Pull-request and main-branch gates

Release-affecting changes must pass:

1. repository Python tests;
2. `tools/validate_native_contract.py`;
3. x64 MSVC builds of both native targets;
4. complete standalone proxy-export validation;
5. x64/static-runtime checks for both Clean Pause images;
6. pinned upstream Ultimate ASI Loader download, SHA-256 verification and x64 validation for the ASI package;
7. release-shaped ZIP construction and integrity checks.

A PR never publishes a GitHub Release. A release-preparation merge to `main` with a new `VERSION` reruns the same gates, creates the immutable matching tag if absent, and publishes only the edition assets currently approved for public distribution.

## Preparing a release

1. Choose the next SemVer version.
2. Set `VERSION`.
3. Move `CHANGELOG.md` entries from `Unreleased` to the target version.
4. Update `docs/RELEASE_NOTES.md` and current support/distribution documentation.
5. If changing the bundled Ultimate ASI Loader, review an official tagged upstream release and update its pinned version, source commit and published asset SHA-256 together in `.github/workflows/release.yml`.
6. Merge only after release-shaped CI is green.
7. The successful main workflow automatically creates the exact `v<VERSION>` tag and GitHub Release.

If a qualifying `push` event is intentionally unavailable or suppressed by the caller, `workflow_dispatch` on the `main` branch is the supported recovery path. It executes the same build/verification/tag/publication jobs; dispatches from non-main refs cannot publish.

## Bundled Ultimate ASI Loader

ASI release packages starting with v0.2.2 include a complete first-install loader path rather than requiring a separate download.

The loader is treated as a pinned third-party release input, not as a floating dependency:

- source is the official `ThirteenAG/Ultimate-ASI-Loader` GitHub repository;
- the workflow pins a specific upstream release version and source commit;
- it downloads the named x64 release asset from that exact tag rather than any `latest` URL;
- the downloaded archive must match the reviewed SHA-256 digest before extraction;
- exactly one `dinput8.dll` must be found and it must validate as x64;
- `ASI_LOADER_SOURCE.txt` records upstream version/commit plus archive and extracted-file hashes;
- the upstream MIT license is copied into the ASI package as `ULTIMATE_ASI_LOADER_LICENSE.txt`.

Users with an existing compatible ASI loader should keep it rather than blindly overwriting `dinput8.dll`.

## Edition-gated publication

Build validation and public distribution are separate concerns. Both native targets remain continuously built so shared-runtime and proxy regressions are caught even if one edition has a temporary distribution blocker.

For **v0.2.2**:

- `KCD2CleanPause.asi` is the retail-accepted public edition;
- its public ZIP includes the pinned official x64 Ultimate ASI Loader for fresh installation;
- `version.dll` is still built, packaged and verified in Actions CI but is not attached to the public release while Defender investigation #38 remains unresolved;
- `SHA256SUMS.txt` covers only public release assets;
- `CI_SHA256SUMS.txt` covers both internally validated ZIPs and remains an Actions artifact rather than a public release asset.

The immutable v0.2.1 ASI archive predates bundled-loader packaging.

When #38 is resolved, standalone publication can be restored in a later release without changing the shared runtime architecture.

## Publication flow

For an unpublished version on a qualifying main push or a manual dispatch from `main`, `.github/workflows/release.yml`:

1. validates `VERSION`;
2. reruns tests/native contract validation;
3. builds both x64 Clean Pause editions;
4. validates the complete 17-export standalone proxy surface and both Clean Pause PE/runtime properties;
5. downloads and verifies the pinned official x64 Ultimate ASI Loader input;
6. constructs both edition ZIPs for CI validation, including loader provenance/license in the ASI package;
7. writes internal checksums for both and public checksums for approved assets;
8. downloads and re-verifies all CI packages before publication;
9. creates the immutable matching tag on the exact workflow commit if absent;
10. creates the GitHub Release with only approved public assets and `--verify-tag`.

## Current edition policy

The ASI and standalone editions are mutually exclusive installations of the same runtime.

- **v0.2.2 ASI:** current public release target; generated with the pinned official x64 Ultimate ASI Loader bundled for fresh installation.
- **new standalone builds:** not publicly distributed until #38 is resolved.
- **v0.2.0 standalone:** remains immutable historical release and was retail-proven for that version, but does not include the later pause-transition fix.

## Validation baseline

Current retail evidence is from **KCD2 1.5.6 on the PC Xbox Store / Xbox app version**. The runtime records build identity/fingerprint data so compatibility evidence can be expanded and revalidated as additional game builds are exercised.
