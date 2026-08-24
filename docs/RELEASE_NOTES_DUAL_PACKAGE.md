## Two installation editions

This release publishes the same Clean Pause runtime in two mutually exclusive packages:

- `kcd2-clean-pause-v<VERSION>-asi.zip` — contains `KCD2CleanPause.asi` and requires a compatible x64 ASI loader, normally installed as `dinput8.dll` beside the game executable / `WHGame.dll`.
- `kcd2-clean-pause-v<VERSION>-version-dll.zip` — contains the standalone `version.dll` proxy and requires no separate ASI loader.

Use the ASI edition if another mod already owns `version.dll` or if you already use an ASI loader. Do not install both Clean Pause editions together.

The Clean Pause runtime and behavior are intentionally identical between editions; only the loading/bootstrap mechanism differs.
