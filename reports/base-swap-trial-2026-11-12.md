# Base swap trial, 12 November 2026 (G9-W6)

`tools/base_swap.py` run on a copy of the repository (`/tmp`), not on any remote branch:
`feature/gen9` at `c69ea1e` rebuilt on a **stand-in for "Gen 8 on main"**: main `62bd8a2`, then
one commit with the snapshot's content (`7d301eb`, the Gen 8 prototype at `ca4fe53`), then
the prototype's two later commits (`ca4fe53..e9fde92`: near-tie probe bots, and "rule bidder r2
(structural fixes)", 8 files, +715 -58). Open PR #20's branch was carried along with `--also`.
Nothing was pushed.

## What the script reported

`origin/feature/gen9` at `c69ea1e98`: main `62bd8a24d` + snapshot `7d301eb6d` + 26 Gen 9 commits (8 merges). New base `beaee179f`.

The snapshot changed 43 files; Gen 9 changed 57.

## Hooks: snapshot files Gen 9 changed again

- `reports/README.md` (+3 -0)

## Drift: snapshot files that differ on the new base

- `bridge_harness/rule_bidder.py`
- `configs/gen8-proto-bots.json`
- `scripts/gen_system_fit.py`
- `scripts/tune_rule_bidder.py`
- `tests/test_rule_bidder.py`

## Replay

Rebuilt as local branch `feature/gen9-rebased-beaee17` at `2bcbb509b`.

Every Gen 9 file change is the same patch as before (57 files).

- `origin/feature/gen9-workflow-tests`: rebased as `feature/gen9-workflow-tests-rebased-beaee17` at `accc1689e`


## Tests on the rebuilt branch

`scripts/run_tests.py --prepare --set gen9` on the rebuilt PR #20 branch (2 CPUs): 15 files, 171
tests passed under unittest. `tests/test_gen9_cards.py` is written for pytest, which the runner
then did not pick up (fixed on PR #20 since); run under pytest it gives **13 passed, 5 failed**
on the rebuilt branch and **18 passed** on `feature/gen9` as it is.

The five failures are `test_rule_bidder_auctions_never_break_their_card`, one per system
(precision, precision-plain, standard, standard-12-14, standard-light), all at the same point:
after 1NT-2H the r2 rule bidder bids **3S** where the card IR's first fitting rule is 2S,
"complete the transfer". Reading: r2 adds a transfer super-accept that the cards compiled from
the rule bidder's settings do not describe. If Gen 8 lands with r2, `bridge_harness/cards/` (bill)
needs that rule; nothing else in the Gen 9 set noticed the change.

## What this says about the swap

- Mechanically it is easy: no conflicts, every Gen 9 file change replays as the same patch, the
  merges are kept, the one hook is a line in `reports/README.md`.
- The risk is semantic, in the drifted files Gen 9 builds on (`rule_bidder.py` here), and only
  tests find it. The base swap (G9-A5) should run the Gen 9 test set on the rebuilt branch before
  `feature/gen9` is pointed at it.
