# ASI retail acceptance

> **Status for v0.2.1:** core ASI loader/runtime path accepted on KCD2 1.5.6 Xbox Store / Xbox app using the upstream Ultimate ASI Loader. Broader coexistence with arbitrary native plugins remains a non-blocking follow-up.

## Accepted installation baseline

- one compatible x64 Ultimate ASI Loader build as `dinput8.dll` beside the game executable / `WHGame.dll`;
- `KCD2CleanPause.asi` beside that loader;
- no Clean Pause standalone `version.dll` loaded at the same time.

## Retail evidence

Cumulative v0.2.1 candidate testing confirmed the ASI module loads and the native runtime is active. The final transition-scoped candidate confirms:

- Xbox Start enters Clean Pause;
- world simulation and ongoing dialogue audio pause together immediately;
- retained HUD/dialogue subtitles no longer show the previous hide/restore transition;
- normal pause DoF is absent from the retained Clean Pause frame;
- second Start or Xbox B reveals the vanilla pause menu;
- normal menu resume returns to gameplay.

This is sufficient for the tested ASI loading path to be the supported v0.2.1 distribution. It does not establish universal compatibility with every ASI plugin or loader fork.

## Coexistence follow-up

Repeat the core checks with representative real KCD2 ASI plugins sharing the same loader. Any conflict found there should be treated as plugin-coexistence compatibility debt rather than retroactively invalidating the already-tested single-loader/single-plugin path.
