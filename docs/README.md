# Documentation

This directory separates current production documentation from historical development evidence.

## Current documentation

Use these files for the current implementation and release process:

- [README](../README.md) — user-facing behavior, installation, uninstall, and tested-version summary.
- [STATUS_AND_PLAN.md](STATUS_AND_PLAN.md) — current release status, accepted product contract, and remaining work.
- [NEXUS.md](NEXUS.md) — prepared Nexus Mods page copy, upload artifact, credits, permissions, and publication checklist.
- [DESIGN.md](DESIGN.md) — active runtime architecture and safety rules.
- [TESTING.md](TESTING.md) — release acceptance and compatibility checks.
- [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md) — acceptance evidence for the ASI loading path.
- [DUAL_PACKAGE.md](DUAL_PACKAGE.md) — ASI and standalone package contract.
- [RELEASE.md](RELEASE.md) — SemVer and tag-driven GitHub Release process.
- [RELEASE_NOTES.md](RELEASE_NOTES.md) — notes for the current stable release.
- [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) — rejected implementation paths that must not be reintroduced without new retail evidence.

When documents disagree, the order of authority is:

1. `README.md` for user-visible behavior and installation;
2. `STATUS_AND_PLAN.md` for current release readiness and open work;
3. `DESIGN.md` for the production architecture;
4. `TESTING.md` and `RELEASE.md` for verification/publication procedure.

## Historical development evidence

Superseded prototypes, research notes, and retail experiments are isolated under [`history/`](history/README.md). They are retained only as an engineering evidence trail and are not implementation or installation instructions.
