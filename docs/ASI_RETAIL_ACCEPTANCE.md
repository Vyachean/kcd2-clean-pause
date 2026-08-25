# ASI retail acceptance

> **Status for v0.2.0:** optional follow-up. The standalone `version.dll` edition is the supported retail-proven release path. The ASI edition is shipped as **experimental** and does not block the stable standalone release.

The ASI edition changes only the loading mechanism. It should not be described as supported until this acceptance pass succeeds on KCD2 1.5.6 Xbox Store / Xbox app.

## Installation baseline

- install one compatible x64 ASI loader as `dinput8.dll` beside the game executable / `WHGame.dll`;
- install `KCD2CleanPause.asi` beside that loader;
- remove the Clean Pause standalone `version.dll` edition before launch.

## Acceptance

- [ ] game starts normally;
- [ ] `kcd2_clean_pause_native.log` is created beside `KCD2CleanPause.asi`;
- [ ] log reports the Clean Pause runtime active;
- [ ] Escape enters Clean Pause;
- [ ] Xbox Start enters Clean Pause;
- [ ] world simulation pauses;
- [ ] audio/dialogue/cutscene progression pauses coherently;
- [ ] current dialogue subtitle remains visible where applicable;
- [ ] current NPC overhead subtitle remains visible where applicable;
- [ ] retained Clean Pause presentation is sharp rather than using the vanilla pause DoF blur;
- [ ] second Escape/Start reveals the vanilla pause menu;
- [ ] Xbox B reveals the vanilla pause menu under the current product contract;
- [ ] normal vanilla pause-menu controls remain functional;
- [ ] returning to gameplay leaves controls and graphics behavior normal;
- [ ] returning to the front end leaves controls normal.

Do not create a separate game launch solely to manufacture subtitle edge cases. Exercise subtitle checks when suitable dialogue occurs during the same acceptance session.

## Coexistence follow-up

After standalone ASI acceptance, repeat the core checks with at least one other real KCD2 ASI plugin installed through the same loader.

Passing these checks is sufficient to remove the experimental label from the ASI edition in a later patch release if no runtime changes are needed. It does not establish universal compatibility with every native plugin.
