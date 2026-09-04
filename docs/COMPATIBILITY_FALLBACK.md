# Conservative compatibility fallback

Exact registered build profiles remain the primary and preferred runtime path.

When an exact/supported profile does not match, Clean Pause may attempt a fallback only when `whdlversions.json` reports a build code in the already implemented `release_1_5-*` family. Other release branches remain unsupported and install no hooks.

The fallback intentionally avoids version-specific roots:

1. `gEnv` is derived from a unique executable reference to the canonical `pConsole` storage using the existing `exec autoexec.cfg` anchor evidence;
2. the candidate environment must fit the release_1_5 `SSystemGlobalEnvironment` layout in readable/writable image memory;
3. the live script/input/game/system/FlashUI interfaces, vtables, main-thread ownership and exact observed game-name identity must all validate before the input hook is installed;
4. ambiguity or any failed proof disables the fallback and leaves vanilla behavior untouched.

The fallback deliberately does **not** reuse a known build's `IGameFramework` RVA, vtable RVA, PauseGame observer, root-HUD pin or Menu-prehide capability. Those remain exact-profile features only. Fallback mode therefore uses the shared PostInputEvent/Menu compatibility path and may provide less polished behavior than a fully registered build.

This is a compatibility bridge, not a support claim for arbitrary future KCD2 ABIs. A new `release_1_6`, `release_2_*`, missing/invalid build metadata, ambiguous anchor, or changed release_1_5 ABI remains fail-closed until independently validated and registered.
