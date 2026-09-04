# Release pipeline

GitHub Releases are the canonical public distribution channel. Generated native binaries/ZIP files are not committed.

## Versioning

The project follows Semantic Versioning (SemVer) with immutable tag-backed releases. Before 1.0, backward-compatible features increment **MINOR** and backward-compatible fixes increment **PATCH**. A release-candidate number increments only when another candidate for the same target release is needed. It is not incremented for every merged PR. v0.3.0 is the current stable release. v0.3.0-rc.1 through rc.5 remain immutable prerelease history.

## Required CI gates

Release-affecting changes must pass repository tests, stable native contract validation, x64 MSVC builds for both editions, standalone export validation, runtime-profile executable tests, pinned Ultimate ASI Loader verification, and release-shaped package integrity checks.

A PR builds release-shaped artifacts but never publishes a GitHub Release.

## Preparing a candidate

1. Update `VERSION`.
2. Add the target to `CHANGELOG.md`.
3. Update `docs/RELEASE_NOTES.md` and current support/compatibility docs.
4. Run release-shaped PR CI.
5. Confirm the release notes accurately disclose known runtime/security-reputation caveats.
6. Merge to `main` to publish the immutable release after the target's project-controlled QA and compatibility gates are accepted.

A qualifying main push with a previously unpublished VERSION automatically creates the exact `v<VERSION>` tag and matching GitHub Release.

## v0.3.0 runtime baseline

Steam 1.5.6 exact-profile runtime is accepted with canonical `gEnv`, anchor validation, CCryAction framework root, lazy PauseGame observer, and repeated Clean Pause/menu/resume cycles.

Xbox / Microsoft Store 1.5.6 exact-profile runtime is accepted with `gEnv` RVA `0x049D6EF8`, static framework object RVA `0x056EC680`, vtable RVA `0x040DAF18`, and repeated Clean Pause/menu/resume cycles.

A diagnostic forced-fallback test on the real Xbox binary proved the conservative release_1_5 fallback resolves the same `gEnv` without borrowing exact framework roots or presentation capabilities.

GOG/Epic exact environment profiles remain implemented but are not yet runtime-tested by this project.

## Edition publication

- v0.3.0 ASI: current stable public release.
- v0.3.0-rc.5 ASI: immutable prerelease history.
- new standalone `version.dll`: CI-only under the current ASI-first edition-publication policy.
- `SHA256SUMS.txt`: only intentionally public assets.
- `CI_SHA256SUMS.txt`: both internally validated packages.

## Antivirus / Smart App Control status (#38)

Known heuristic/ML detections are disclosed with clear source/build provenance, but antivirus or Smart App Control verdicts are **not release gates by themselves**.

Issue #38 tracks platform compatibility/reputation. Vendor submissions and reclassification results are useful evidence and should be recorded when pursued, but a Microsoft/Symantec/Cynet clean verdict is not required for prerelease or stable promotion.

A release is blocked only by project-controlled evidence such as failed QA/compatibility gates, broken provenance, an unexplained source/artifact mismatch, or evidence of actual malicious/compromised behavior. No packing, obfuscation, payload renaming, or similar AV-evasion work is part of the release process.

## Publication flow

For an approved unpublished VERSION on `main`, the workflow reruns all tests/build/package checks, verifies the pinned ASI loader, creates the immutable tag if absent, and publishes only approved assets. Prerelease versions are marked as prereleases automatically.
