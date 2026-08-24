# v0.1.0-rc.7g — borrowed movieclip ownership correction

Prerelease candidate for Kingdom Come: Deliverance II 1.5.6 Windows retail, primarily Xbox Store / Xbox app.

## Retail status

RC7g has now passed the core pause/menu lifecycle on Xbox Store KCD2 1.5.6.

Confirmed sequence:

1. first Start/Escape -> Clean Pause without drawing the vanilla pause menu;
2. subtitle remains visible at the bottom;
3. second Start/Escape -> ordinary KCD2 pause menu appears;
4. that visible menu can then be exited normally;
5. no crash occurs in this sequence.

This closes the two crash regressions introduced by RC7e and RC7f.

## Why rc7g exists

RC7e proved that preserving KCD2's 28 HUD child movie clips can keep the current subtitle visible during Clean Pause, but its raw movieclip pointers were retained across frames and the build later crashed after revealing the ordinary pause menu.

RC7f switched to bool-only snapshots but immediately called `Release()` on every `IUIElement::GetMovieClip()` result. It then crashed on the first pause immediately after the complete 28-child gameplay snapshot.

RC7g corrects the ownership model without discarding the successful 28-child presentation mechanism.

## Accepted ownership model

RC7g treats `IUIElement::GetMovieClip()` results as borrowed/cached pointers:

- use only inside the current capture/restore helper call;
- never persist a movieclip pointer in global/snapshot state;
- never call `Release()` on `GetMovieClip()` results;
- keep only 28 visibility booleans in each snapshot.

This model now has both static API support and positive retail validation.

## Dual exact snapshots

RC7g keeps two bool-only snapshots:

- gameplay HUD snapshot before forwarding physical pause;
- vanilla-pause HUD snapshot after KCD2 opens its real pause and before gameplay HUD restoration.

Transitions:

- Running -> Clean Pause: restore gameplay snapshot;
- second Start/Escape: restore vanilla-pause snapshot before revealing Menu;
- direct B: restore vanilla-pause snapshot before replaying vanilla pause toggle;
- fail-open while paused: best-effort vanilla-pause snapshot first.

`Menu@0::Render()` remains presentation-only.

## HUD/update path

Verified `IUIElement::Update(float)` slot 23 remains the bounded main-thread maintenance route. RC7g includes one-shot before/after-trampoline markers for crash localization.

The successful first-pause retail result means this Update hook is no longer a current crash blocker.

## Safety contract

Generated-source CI rejects:

- any `ReleaseFlashVariable` helper;
- any `kFlashVariableReleaseSlot` / `FlashVariableReleaseFn` use in candidate source;
- persisted `snapshot.clip` / `HudClipSnapshot` state;
- HUD child work from `Menu::Render()`;
- rejected PauseGame, `only_ui`, action-map, root-HUD and fixed-RVA paths.

CI requires:

- exactly 28 named HUD clips;
- call-local movieclip acquisition;
- no Release operation in capture/restore;
- exact visibility bool replay;
- dual gameplay/vanilla-pause snapshots;
- main-thread-only periodic HUD mutation;
- direct-B vanilla replay route and nested-input protection.

## Remaining retail gates

The following are **not** implied by the successful core sequence and remain open:

1. direct Xbox B from Clean Pause -> Running;
2. current subtitle surviving beyond its normal lifetime while paused;
3. dialogue/cutscene progression resuming the same line/state after Clean Pause;
4. repeated cycles / optional Alt-Tab or load-transition robustness.

These should be bundled into a normal future session rather than requiring separate game launches.

See `docs/RETAIL_EVIDENCE_RC7G.md`, `docs/STATUS_AND_PLAN.md`, and `docs/REJECTED_HYPOTHESES.md` for the current evidence ledger.
