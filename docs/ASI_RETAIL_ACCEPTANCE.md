# ASI retail acceptance

The ASI edition changes only the loading mechanism. It is not considered retail-equivalent to the established standalone `version.dll` path until this acceptance pass succeeds on the target KCD2 1.5.6 Xbox Store / Xbox app build.

This checklist applies to the `0.2.0` release line and follows the current product contract documented in [README.md](../README.md) and [DESIGN.md](DESIGN.md).

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

Prefer a plugin that demonstrates the reason the ASI edition exists — for example, a setup where another native mod would otherwise conflict with the standalone Clean Pause `version.dll`.

Passing this follow-up proves file-level coexistence and provides evidence against hook-order regressions. It does not establish universal compatibility with every native plugin.
