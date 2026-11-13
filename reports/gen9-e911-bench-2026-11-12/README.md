# E9-11 on the reading bench: the replayed house bidder against the hand-fit scorer

Gen 9 research (sam, signals), 13 November 2026, for E9-11 (owner bill) at g9's request: the verdict from the
bench by a lead other than the owner. Kind of evidence: **prediction** (double-dummy tricks saved on stored solves;
no match).

## Question

E9-11's hypothesis: `9r-32` (the Gen 8 prototype `8p-32` plus the replay reader: the house bidder replayed on the
pool after the opening lead, the scorer still drawing the pool) beats `8p-32` by +0.15 IMPs a board or more. At
p41's 3.6 IMPs a trick that is about +0.042 tricks a board on this bench.

## Data and method

- p41's published pools (`transfer/gen8-p41-reading-pools-20261112`): 530 tables, 21,417 decisions of every seat
  after the opening lead, 329 deals, every stored layout solved once. "A board" is p41's unit, the four seats of one
  table, which is what one bot decides over a board's two tables. Standard errors by deal.
- `scripts/gen9_replay_terms.py` (run with `feature/gen9-bidding-cards` 82ab89f on the path): for each stored layout
  and the true deal, each hidden seat's original hand replayed through the house bidder (`ReplayReader`, profile
  `house-gen6`, eps 0.02, as `9r-32` builds it through `replay_factory`), and the hand-fit scorer's term for the same
  hand and calls. The scorer terms summed over the two hidden seats reproduce p41's `scw` files to 3e-5 nats. Each
  seat is also flagged if its actual calls are the house bidder's own arg max on its true hand: 96.7% of decisions
  have both hidden seats so. Of the 2,120 table seats, 44 are not: 42 seats of bots `1`, `5RZ32` and `ben64` (their
  other tables have common auctions the house bidder made) and 2 seats on 6-32 self-play tables (not looked into).
- `scripts/gen9_reading_bench.py replay`: the readings are `proto` (8p-32's stored reading, net v4 at 1) plus
  replay - scorer on the hidden seats, as `gen9.Gen9Player.replay_correction` adds it (it divides the term by the
  reading's exponent, so the bench's exponent rule treats it as the player does).
  - `rpl`: every hidden seat whose calls are the house bidder's (what 9r-32 does against house bidders).
  - `rplall`: every hidden seat.
  - `rplpar`, `rplopp`: partner's seat only, the opponents' only.
  - `rplonly`: rpl's term with no play reading, against no reading at all (the calls alone, replay against scorer).
- `scripts/gen9_e911_slices.py`: paired by slice; a slice's figure is its share of the per-board total, so slices
  that split the decisions add up. Full output: `slices.txt`, `slices.json`.

## Result

Tricks a board against `proto` (the reading 8p-32 has), nats a decision beside:

| Slice | Decisions | `rpl` | `rplpar` (partner only) | `rplopp` (opponents only) | Nats, `rpl` |
| --- | ---: | ---: | ---: | ---: | ---: |
| All | 21,417 | +0.021 ± 0.016 | +0.014 ± 0.006 | +0.011 ± 0.015 | +0.32 |
| Declarer deciding | 11,212 | +0.005 ± 0.011 | 0 | +0.005 ± 0.011 | +0.24 |
| Defender deciding | 10,205 | +0.016 ± 0.011 | +0.014 ± 0.006 | +0.007 ± 0.011 | +0.41 |
| Hidden seats played by house bots | 13,201 | -0.001 ± 0.012 | +0.008 ± 0.005 | -0.006 ± 0.012 | +0.32 |
| Other decisions | 8,216 | +0.022 | +0.006 | +0.017 | |
| Hidden seats only passed | 4,863 | +0.001 ± 0.007 | 0 | +0.001 ± 0.007 | +0.07 |
| A hidden seat bid once | 7,247 | +0.011 ± 0.009 | +0.008 ± 0.005 | +0.006 ± 0.008 | +0.27 |
| A hidden seat bid twice or more | 9,307 | +0.009 ± 0.011 | +0.006 ± 0.004 | +0.004 ± 0.011 | +0.48 |

("Other decisions" is all minus the house-played slice; its standard error is not computed separately.)

- `rplall` is within 0.002 tricks of `rpl` everywhere: replaying the 3.3% of decisions whose calls were not the
  house bidder's changes nothing measurable.
- Before the deal list `rpl` gives +0.014 ± 0.013 (+0.48 nats), from it on +0.007 ± 0.008 (+0.15 nats).
- Effective layouts, median over decisions: 67 with `rpl` against 108 with `proto`; before the deal list 196 against
  268 (bill's pilot logged 208 against 279 on its pools).
- The calls alone (`rplonly` against no reading): +0.069 ± 0.017 tricks a board, +0.37 nats. On top of the play
  reading the same term gives +0.021: most of what the replay adds about the hidden hands, the cards played also say.
  The play reading alone (`proto` against no reading) is +0.185 ± 0.029 for +0.65 nats.

## Verdict for E9-11

The bench predicts `9r-32` against `8p-32` at +0.021 ± 0.016 tricks a board on all decisions (+0.08 ± 0.06 IMPs at
3.6 a trick), and -0.001 ± 0.012 on the decisions whose hidden seats were played by house bots, which is the match's
population (both sides there are house bots). On that slice's own 396 tables it is -0.001 ± 0.016 tricks a board,
so +0.042 is more than two standard errors away. Both figures are under g9's 0.03-tricks line for spending box time.
Bill's sandbox pilot (-0.27 ± 0.21 IMPs, 200 boards, eps 0) agrees within its error.

The part of the term with a clear sign is partner's calls read by a defender: +0.014 ± 0.006 tricks a board on all
decisions, +0.008 ± 0.005 on the house-played slice (about +0.03 to +0.05 IMPs).

Evidence: this report; `slices.txt`; p41's pools with `rpl-*.npz` and `fit-rpl*-*.npz` (not committed: 136 parts
of derived data, rebuilt by the two commands below in about ten minutes on two cores).
Sample: 21,417 decisions on 530 tables of 329 deals (13,201 decisions on 396 tables with house bots in both hidden
seats); a double-dummy proxy, with the tree off and no tie-break.
Revisit if: a box match of 9r-32 against 8p-32 (e9-11-r8) is run and differs from +0.08 IMPs by more than its error,
or the bench's tricks-to-IMPs rate is found wrong for reading changes, or the replay is used with a different
eps or temperature, or the reading of partner's calls alone is tried at the table.

## Commands

```
PYTHONPATH=<checkout of feature/gen9-bidding-cards> python scripts/gen9_replay_terms.py --pools POOLS --root <that checkout> --shard 0/2   # and 1/2
python scripts/gen9_reading_bench.py replay --out POOLS
python scripts/gen9_e911_slices.py --out POOLS --pair rpl:proto --pair rplall:proto --pair rplpar:proto --pair rplopp:proto --pair rplonly: --pair proto: --json slices.json
```
