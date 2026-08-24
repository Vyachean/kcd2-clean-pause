# ASI retail acceptance

The ASI edition intentionally changes only the loading mechanism. It is not considered retail-equivalent to the established standalone `version.dll` edition until the following acceptance pass succeeds on the target KCD2 1.5.6 Xbox Store / Xbox app build.

## Installation baseline

- install one compatible x64 ASI loader as `dinput8.dll` beside the game executable / `WHGame.dll`;
- install `KCD2CleanPause.asi` beside that loader;
- remove the Clean Pause `version.dll` edition before launch.

## Acceptance

- [ ] game starts normally;
- [ ] `kcd2_clean_pause_native.log` is created beside `KCD2CleanPause.asi`;
- [ ] log reports the Clean Pause runtime active;
- [ ] Escape enters Clean Pause;
- [ ] Xbox Start enters Clean Pause;
- [ ] world simulation pauses;
- [ ] audio/dialogue/cutscene progression pauses coherently;
- [ ] current subtitle remains visible;
- [ ] second Escape/Start reveals the vanilla pause menu;
- [ ] Xbox B reveals the vanilla pause menu as specified by the v0.1.0 input contract;
- [ ] normal vanilla pause-menu controls remain functional;
- [ ] returning to gameplay leaves controls normal;
- [ ] returning to the front end leaves controls normal.

## Coexistence follow-up

After standalone ASI acceptance, repeat the core checks with another real KCD2 ASI plugin installed through the same loader. Prefer a plugin that otherwise conflicts with the standalone Clean Pause package by owning `version.dll`, such as a mod that offers its own ASI alternative.

Passing this follow-up proves file-level coexistence and provides evidence against hook-order regressions. It does not establish universal compatibility with every native plugin.
