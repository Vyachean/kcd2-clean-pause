# Documentation

This directory contains both current project documentation and historical development evidence.

## Current documentation

Use these files for the current implementation and release process:

- [README](../README.md) — user-facing behavior, installation, uninstall, and tested-version summary.
- [STATUS_AND_PLAN.md](STATUS_AND_PLAN.md) — current release status, accepted product contract, and remaining work.
- [NEXUS.md](NEXUS.md) — prepared Nexus Mods page copy, upload artifact, credits, permissions, and publication checklist.
- [DESIGN.md](DESIGN.md) — active runtime architecture and safety rules.
- [TESTING.md](TESTING.md) — release acceptance and compatibility checks.
- [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md) — additional acceptance evidence for the ASI loading path.
- [DUAL_PACKAGE.md](DUAL_PACKAGE.md) — ASI and standalone package contract.
- [RELEASE.md](RELEASE.md) — SemVer and tag-driven GitHub Release process.
- [RELEASE_NOTES.md](RELEASE_NOTES.md) — notes for the current stable release.
- [REJECTED_HYPOTHESES.md](REJECTED_HYPOTHESES.md) — rejected implementation paths that must not be reintroduced without new retail evidence.

When documents disagree, the order of authority is:

1. `README.md` for user-visible behavior and installation;
2. `STATUS_AND_PLAN.md` for current release readiness and open acceptance work;
3. `DESIGN.md` for the production architecture;
4. `TESTING.md` and `RELEASE.md` for verification/publication procedure.

## Historical research and evidence

The following files are retained as an engineering evidence trail. They describe experiments or intermediate candidates and are **not current implementation instructions**:

- [RESEARCH.md](RESEARCH.md)
- [FILTER_PROTOTYPE.md](FILTER_PROTOTYPE.md)
- [PURE_MOD_REFERENCES.md](PURE_MOD_REFERENCES.md)
- [PURE_PROFILE_PLAN.md](PURE_PROFILE_PLAN.md)
- [RC5_DIAGNOSTIC.md](RC5_DIAGNOSTIC.md)
- [RETAIL_TEST1.md](RETAIL_TEST1.md)
- [ROOT_VERSION_RESEARCH.md](ROOT_VERSION_RESEARCH.md)
- [RETAIL_EVIDENCE_RC7C.md](RETAIL_EVIDENCE_RC7C.md)
- [RETAIL_EVIDENCE_RC7D.md](RETAIL_EVIDENCE_RC7D.md)
- [RETAIL_EVIDENCE_RC7E.md](RETAIL_EVIDENCE_RC7E.md)
- [RETAIL_EVIDENCE_RC7F.md](RETAIL_EVIDENCE_RC7F.md)
- [RETAIL_EVIDENCE_RC7G.md](RETAIL_EVIDENCE_RC7G.md)

Names such as `rc.5`, `rc7g`, or `v0.1.0-rc.*` in those files refer to historical development candidates and are retained only as project history.
