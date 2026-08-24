# Release pipeline

GitHub Releases are the canonical distribution channel. Generated native binaries/ZIP files are not committed.

## Production source

Both editions compile the same Clean Pause runtime from `native/src/clean_pause_native.cpp`.

The edition-specific bootstrap files are:

```text
ASI edition
  native/src/asi_entry.cpp

Standalone edition
  native/src/version_proxy.cpp
  native/src/version.def
```

Installation text is also edition-specific:

```text
native/INSTALL_ASI.txt
native/INSTALL_VERSION_DLL.txt
```

Experimental Lua/profile material remains only as historical research and is not packaged.

## Pull-request gates

For release-affecting PRs:

1. repository Python tests run;
2. historical Lua syntax is checked;
3. `tools/validate_native_contract.py` enforces the current native safety/architecture contract;
4. Windows MSVC builds both x64 Release targets;
5. the standalone `version.dll` proxy exports are validated;
6. both native images are verified as x64 and dynamic MSVC runtime dependencies are rejected;
7. `.github/workflows/release.yml` runs its real build/package job but does not publish on `pull_request`.

## Publication

When a release `VERSION` reaches `main`, `.github/workflows/release.yml`:

1. verifies `VERSION` and resolves `v<VERSION>`;
2. reruns tests and native contract validation;
3. builds both x64 native editions on Windows;
4. packages exactly two ZIP assets:

```text
kcd2-clean-pause-v<VERSION>-asi.zip
  KCD2CleanPause.asi
  INSTALL.txt

kcd2-clean-pause-v<VERSION>-version-dll.zip
  version.dll
  INSTALL.txt
```

5. writes one `SHA256SUMS.txt` covering both ZIPs;
6. uploads the exact files as an Actions artifact;
7. downloads and re-verifies checksums, ZIP integrity, and exact ZIP contents in the publish job;
8. creates the matching GitHub Release and tag on the exact workflow commit.

Plain semantic versions such as `0.1.1` are stable. Versions containing `-` are prereleases.

## Edition policy

The ASI and standalone editions are mutually exclusive installations of the same runtime. They must not be installed together.

- Prefer the ASI edition when the user already has a compatible ASI loader or another mod owns `version.dll`.
- Keep the standalone `version.dll` edition for users who want a self-contained installation and have no conflicting `version.dll` mod.

See [DUAL_PACKAGE.md](DUAL_PACKAGE.md) for the packaging contract.

## Version support

The runtime remains pinned to KCD2 **1.5.6** ABI facts verified during development. A future KCD2 update requires revalidation before claiming support; fixed offsets/semantics must not silently be assumed compatible.

The standalone loading path is already retail-proven on the primary Xbox Store target. The ASI loading path requires its own retail acceptance before a stable release claims parity; see [ASI_RETAIL_ACCEPTANCE.md](ASI_RETAIL_ACCEPTANCE.md).
