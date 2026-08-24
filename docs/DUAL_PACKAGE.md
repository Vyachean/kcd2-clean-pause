# Dual native packages

KCD2 Clean Pause ships the same native runtime in two mutually exclusive editions.

## ASI edition

Release asset:

```text
kcd2-clean-pause-v<VERSION>-asi.zip
```

Contents:

```text
KCD2CleanPause.asi
INSTALL.txt
```

This edition requires a compatible x64 ASI loader, normally Ultimate ASI Loader installed as `dinput8.dll` beside the KCD2 executable / `WHGame.dll`.

Use this edition when another mod already owns `version.dll`, or when the user already has a shared ASI loader for other plugins.

## Standalone version.dll edition

Release asset:

```text
kcd2-clean-pause-v<VERSION>-version-dll.zip
```

Contents:

```text
version.dll
INSTALL.txt
```

This edition includes its own Windows `version.dll` proxy bootstrap and requires no separate ASI loader.

Do not use it when another mod already installs an unrelated `version.dll` beside the game executable.

## Runtime identity

Both editions compile the same `clean_pause_native.cpp` runtime and therefore must have identical Clean Pause behavior. The only intended difference is bootstrap/loading:

```text
ASI loader -> KCD2CleanPause.asi -> clean_pause::Start()

KCD2 -> version.dll proxy -> clean_pause::Start()
```

The editions are mutually exclusive. Installing both would load the same runtime twice and is unsupported.

## Release contract

Every release must publish both ZIPs plus one `SHA256SUMS.txt` covering both assets. CI verifies:

- both native images exist and target x64;
- neither image depends on the dynamic MSVC runtime;
- the standalone image still exports the required Windows version APIs;
- the ASI ZIP contains exactly `KCD2CleanPause.asi` and `INSTALL.txt`;
- the standalone ZIP contains exactly `version.dll` and `INSTALL.txt`.
