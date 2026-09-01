# Release pipeline

GitHub Releases are the canonical public distribution channel. Generated native binaries/ZIP files are not committed.

## Versioning policy

The project follows Semantic Versioning with immutable tag-backed releases.

- Stable releases use vMAJOR.MINOR.PATCH.
- Prereleases use vMAJOR.MINOR.PATCH-rc.N (or alpha / beta where appropriate).
- Before 1.0, backward-compatible features increment **MINOR**; backward-compatible fixes increment **PATCH**.
- A release candidate number increments only when another candidate for the same target release is needed. It is not incremented for every merged PR.
- Published tags/releases are immutable and are never moved or recycled.

The current multi-store compatibility work is a feature-level change, so its target stable version is v0.3.0. v0.3.0-rc.1 remains immutable history; v0.3.0-rc.2 is the current acceptance candidate after the Steam RC1 readiness result required a runtime lifecycle fix.

## Production source

Both native editions compile the same Clean Pause runtime. Edition-specific bootstrap files are native/src/asi_entry.cpp and native/src/version_proxy.cpp / native/src/version.def.

## Pull-request and main-branch gates

Release-affecting changes must pass:

1. repository Python tests;
2. tools/validate_native_contract.py;
3. x64 MSVC builds of both native targets;
4. complete standalone proxy-export validation;
5. x64/static-runtime checks for both Clean Pause images;
6. runtime-profile executable tests when enabled by Validate;
7. pinned upstream Ultimate ASI Loader download, SHA-256 verification and x64 validation for the ASI package;
8. release-shaped ZIP construction and integrity checks.

A PR never publishes a GitHub Release. A release-preparation merge to main with a new VERSION reruns the same gates, creates the immutable matching tag if absent, and publishes only the edition assets currently approved for public distribution.

## Preparing a release

1. Choose the next SemVer version.
2. Set VERSION.
3. Move CHANGELOG.md entries from Unreleased to the target version.
4. Update docs/RELEASE_NOTES.md and current support/distribution documentation.
5. If changing the bundled Ultimate ASI Loader, review an official tagged upstream release and update its pinned version, source commit and published asset SHA-256 together in .github/workflows/release.yml.
6. Merge only after release-shaped CI is green.
7. The successful main workflow automatically creates the exact `v<VERSION>` tag and GitHub Release.

If a qualifying push event is intentionally unavailable or suppressed, workflow_dispatch on main is the supported recovery path. Dispatches from non-main refs cannot publish.

## Release-candidate acceptance flow

For compatibility work that still needs real game acceptance:

1. publish an immutable GitHub prerelease through the normal main release workflow;
2. test the published ASI artifact rather than an ad-hoc local/CI binary;
3. if a runtime change is required, increment the RC number and publish a new immutable prerelease; never move or reuse an old RC tag;
4. if the RC is accepted, prepare stable v0.3.0 from the same accepted runtime implementation with only release/version/documentation promotion changes;
5. publish the stable GitHub artifact first;
6. use that stable GitHub artifact for Nexus Mods.

The RCs remain immutable history after stable promotion.

## Bundled Ultimate ASI Loader

ASI release packages starting with v0.2.2 include a complete first-install loader path rather than requiring a separate download.

The loader is treated as a pinned third-party release input:

- source: official ThirteenAG/Ultimate-ASI-Loader repository;
- workflow pins a specific upstream release version and source commit;
- it downloads the named x64 release asset from that exact tag;
- the downloaded archive must match the reviewed SHA-256 digest;
- exactly one dinput8.dll must be found and validate as x64;
- ASI_LOADER_SOURCE.txt records provenance and hashes;
- ULTIMATE_ASI_LOADER_LICENSE.txt carries the upstream MIT license.

Users with an existing compatible ASI loader should keep it rather than blindly overwriting dinput8.dll.

## Edition-gated publication

Build validation and public distribution are separate concerns. Both native targets remain continuously built so shared-runtime and proxy regressions are caught even while one edition has a distribution blocker.

Current policy:

- v0.2.2 ASI is the current stable public release.
- v0.3.0-rc.2 ASI is the current multi-store/Steam-readiness prerelease candidate.
- v0.3.0-rc.1 remains immutable prerelease history and must not be retagged or replaced.
- New standalone version.dll builds remain CI-only while Defender investigation #38 is unresolved.
- SHA256SUMS.txt covers only public release assets.
- CI_SHA256SUMS.txt covers both internally validated ZIPs and remains an Actions artifact.

When #38 is resolved, standalone publication can be restored in a later release without changing the shared runtime architecture.

## Publication flow

For an unpublished version on a qualifying main push or manual dispatch from main, .github/workflows/release.yml:

1. validates VERSION;
2. reruns tests/native contract validation;
3. builds both x64 Clean Pause editions;
4. validates the complete 17-export standalone proxy surface and both Clean Pause PE/runtime properties;
5. downloads and verifies the pinned official x64 Ultimate ASI Loader input;
6. constructs both edition ZIPs for CI validation;
7. writes internal checksums for both and public checksums for approved assets;
8. downloads and re-verifies all CI packages before publication;
9. creates the immutable matching tag on the exact workflow commit if absent;
10. creates the GitHub Release with only approved public assets and --verify-tag;
11. marks the release as a GitHub prerelease automatically when VERSION contains a prerelease suffix.

## Current validation baseline

- Xbox / Microsoft Store KCD2 1.5.6 is the existing Clean Pause runtime-tested baseline.
- Steam KCD2 1.5.6 release_1_5-15693 is the v0.3.0-rc.2 acceptance target. RC1 already confirmed exact build/profile/canonical-environment identity and eliminated the prior crash, but exposed the startup-readiness timeout.
- GOG and Epic Games Store release_1_5-15693 profiles are implemented from distribution-specific reverse-engineering/runtime evidence but are not yet claimed as Clean Pause runtime-tested.
- Unknown or mismatched builds fail closed before version-specific hooks.
