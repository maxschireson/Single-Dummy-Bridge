# What the play-reading is worth, net by net (Gen 8 prototype)

12 November 2026. A double-dummy proxy study, not paired cardplay; the matches it is compared with
were played by the Gen 8 session and are quoted from `box/coordination`.

## Question

The Gen 8 prototype (`8p-32`) weighs layouts by the policy net's probability of the hidden seats'
plays, from trick 1. Played alone, the nets differ by whole IMPs a board (v4 beats v0 by
4.05 +- 0.09, v4.1 beats v4 by 0.76 +- 0.07); inside the bot the swap is hard to see in a match.
How much is the reading worth with each net, and can a better net reach the result through it?

## Answer

The reading gets better from v0 to v4 and is flat from v4 on. 530 tables, 21,417 decisions, 329
deals; double-dummy tricks saved on the true deal against no reading, per board (the four seats of
one table, which is what one bot decides over a board's two tables):

| Net | True layout's log-weight gained, nats | Tricks saved a board | Against v0, same decisions | Against v4 |
| --- | --- | --- | --- | --- |
| v0 | +0.353 | +0.117 +- 0.028 | | -0.069 +- 0.024 |
| v2 | +0.504 | +0.172 +- 0.031 | +0.055 +- 0.024 | -0.013 +- 0.017 |
| v4 | +0.649 | +0.185 +- 0.029 | +0.069 +- 0.024 | |
| v4.1 | +0.688 | +0.198 +- 0.029 | +0.081 +- 0.024 | +0.012 +- 0.015 |
| 512 wide, five epochs | +0.692 | +0.169 +- 0.030 | +0.053 +- 0.026 | -0.016 +- 0.022 |

At about 3.6 IMPs a trick (the rate in the arena's fork pairs) v0 to v4 is about +0.25 IMPs a
board, 6% of what separates those nets played alone, and v4 to v4.1 about +0.04. The matches:
`8p-32` with v4 against with v0, +0.040 +- 0.112 (1,000 boards); with v4.1 against with v4,
-0.036 +- 0.080 (1,600 boards).

What limits it is the amount of information, not its aim. Information about honours is worth four
to five times as much a nat as information about small cards, and the nets' nats convert at the
honours' rate. There are few of them: 0.69 nats a decision with v4.1, 0.04 more than with v4.

## Data, nets, settings

- Tables: root tables of arena boards fetched after 03:59 UTC on 12 November (the four fresh sets
  B to E of the policy 4.1 run; fetch manifests under `training/policy-v4.1-20261112/` on
  `transfer/gen7-policy-v4.1-20261112`), deals in v4.1's training families left out. 6-32
  self-play and 7s-32 against other bots. At 13,201 of the decisions (on 396 tables) both hidden
  seats were played by house bots; that subset gives the same picture (`t2-house.txt`).
- Decisions: every decision after the opening lead with a choice of cards, all four seats: 40.4 a
  table, 10,683 before the deal list and 10,734 from it on.
- Nets: `models/cardplay/gen7-policy-v0-2026-11-11`, `-v2-`, `-v4-`, `gen7-policy-v4.1-2026-11-12`,
  and the unpackaged 512-wide five-epoch net of the 4.1 run (`runs/w512e5/policy_epoch5_T.npz` on
  `transfer/gen7-policy-v4.1-box-20261112`). No net trained on any of these deals.
- Settings: `8p-32`'s (`play_weight` 1.0, `early_play_weight` 1.0, `early_pool` 512,
  `early_min_effective` 8, `play_floor` 0.05, `play_lead`) on the live 6-32 search after the lead
  (32 layouts solved; from the deal list, up to 256). The tree is off and the tie-break is left
  out: a decision's cost is the mean over the cards the weighted solves rate equal best.

## Method

`scripts/gen8_reading_bench.py` (branch `feature/gen8-p41-20261112`).

`pools` replays each table. At each decision it takes the layouts the engine would weigh: before
the deal list the pool `Gen7Player.early_layouts` draws by the hand-fit scorer's class weights,
the same draw for every net; from the deal list on, the listed layouts. Every one is solved once,
double dummy, for every legal card, and so is the true deal. Each net's floored log-probability
of the hidden seats' plays is stored for every layout and for the true one, split into the opening
lead, partner's other plays and the opponents'.

`report` then scores any reading on the stored solves. "As the engine does it" is the
`early_min_effective` rule followed by 32 layouts resampled from the pool, averaged over eight
evenly spaced resampling offsets (from the deal list: every listed layout, 256 resampled above
that). Standard errors take the deal as the unit. Because the layouts and solves are shared, the
differences between nets are paired.

The true layout's gain in log-weight before the deal list is `fit(true) - log mean exp(fit(pool))`,
an estimate that runs a little high with a finite pool, equally for every net.

## Results beyond the table

By stage of the play, tricks saved a board (`t2.txt`):

| | Tricks 1-2 | 3-4 | 5-6 | 7-9 | 10-13 | Declarer deciding | Defender deciding |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v0 | +0.019 | +0.024 | +0.037 | +0.035 | +0.002 | +0.070 | +0.047 |
| v4 | +0.020 | +0.043 | +0.068 | +0.049 | +0.006 | +0.101 | +0.084 |
| v4.1 | +0.028 | +0.037 | +0.077 | +0.051 | +0.004 | +0.101 | +0.097 |

Other settings on the same solves, v4.1 unless said (`t2-sweep.txt`):

- Exponent: 0.25 +0.115, 0.5 +0.158, 0.75 +0.184, 1.0 +0.198, 1.5 +0.174, 2 +0.138, 3 +0.070.
  Every net peaks at 1.0 except the five-epoch one (0.75: +0.180 against +0.169 at 1.0).
- The `early_min_effective` rule never fires: the mean exponent used is 1.00 and the median
  effective pool before the deal list is 234 (five epochs) to 322 (v0) layouts of 512.
- Pool size before the deal list: 128, 256, 512 give +0.129, +0.140, +0.143 there.
- Layouts solved: 128 resampled in place of 32 before the deal list gives +0.174 against +0.143
  there, and about the same +0.03 with every net.
- Whose plays: the opponents' alone +0.130, partner's alone +0.033, the opening lead alone +0.020.
- Cost: with no reading 0.0181 tricks a decision (0.73 a board), with v4.1's reading 0.0132 (0.53).
  With every stored layout weighted, v4.1's reading costs 0.0123 a decision and its own weights
  expect 0.0133: the weights are uncertain, not wrong.

The owner head as layout weights (`owners`, `report --owner`, `t2-owner.txt`): the product of the
head's per-card probabilities over the pool, from the decider's view. Alone it saves at most
+0.034 a board with any net; added to the reading it loses (v4.1, half weight: +0.173 against +0.198).

### Where the information sits (`report --mechanism`, `t2-mechanism.txt`)

Mean log-probability, under the weights, that an unseen card is where it truly is (cards either
hidden hand could hold; -0.693 is a coin toss):

| | No reading | v0 | v2 | v4 | v4.1 | Five epochs |
| --- | --- | --- | --- | --- | --- | --- |
| Before the deal list, honours (T to A) | -0.613 | -0.585 | -0.569 | -0.557 | -0.556 | -0.556 |
| Before the deal list, small cards | -0.640 | -0.621 | -0.615 | -0.608 | -0.607 | -0.607 |
| Deal list, honours | -0.544 | -0.478 | -0.443 | -0.405 | -0.398 | -0.397 |
| Deal list, small cards | -0.576 | -0.515 | -0.491 | -0.451 | -0.449 | -0.450 |

Information aimed at the true deal: each layout's log-weight raised by k for every card (of a kind)
it gives to its true holder. The true layout's gain in nats, then tricks saved a board:

| Aimed at | k 0.125 | k 0.25 | k 0.5 | k 1 | k 2 |
| --- | --- | --- | --- | --- | --- |
| Every unseen card | 0.68: +0.104 | 1.30: +0.182 | 2.41: +0.361 | 4.07: +0.543 | 6.02: +0.540 |
| Honours only | 0.25: +0.078 | 0.48: +0.135 | 0.88: +0.243 | 1.50: +0.403 | 2.17: +0.493 |
| Small cards only | 0.43: +0.023 | 0.83: +0.050 | 1.54: +0.108 | 2.64: +0.162 | 3.93: +0.145 |

(Standard errors 0.01 to 0.045 tricks.) A nat about honours is worth about 0.28 tricks a board, a
nat about small cards about 0.06. The nets sit at 0.24 to 0.34 tricks a nat (v4.1: 0.69 nats,
+0.198, so 0.29), on the honours' line. Twice v4.1's nats, aimed as well, would be worth about
+0.17 tricks a board more. The curve tops out near +0.54 because the pool holds 512 layouts and the search
solves 32 of them; a bot told the deal gains the whole 0.73 against no reading, and about 0.54
against `8p-32`.

## The tree, by net and by layouts

Not part of the reading, measured the same morning because it is the other place the net enters
(`scripts/gen7_bench.py`, `scripts/gen7_sweep.py` on `transfer/gen7-policy-v4.1-20261112`; 1,761
fresh gap-fork pairs at 6-32's decisions on 666 deals; regression of the forced card's realized
cost on the search's gap and the tree's correction; `treeA_*.txt`, `treeB_v4_l32.txt`):

| Tree | Coefficient of the correction | Sd of the correction | Trust it supports |
| --- | --- | --- | --- |
| v4, 8 layouts (as launched) | +0.251 +- 0.071 | 0.321 | 0.29 [0.14, 0.45] |
| v4.1, 8 layouts | +0.263 +- 0.082 | 0.282 | 0.31 [0.12, 0.50] |
| v0, 8 layouts | +0.151 +- 0.060 | 0.407 | 0.18 [0.04, 0.30] |
| v4, 32 layouts | +0.263 +- 0.078 | 0.275 | 0.31 [0.15, 0.49] |

The same shape: v0's tree is worth less than v4's, v4.1's is no better than v4's, and four times
the layouts gives a quieter correction that deserves no more trust. In the arena's own audit
tables the launched tree's overrides gained 0.046 +- 0.014 tricks each (3,045 audited overrides,
all with v4; `training/policy-v4.1-20261112/near-tie/tree_overrides.txt` on the transfer branch).

## Limits

- Double-dummy cost on the true deal is a proxy. It says nothing of what a card does to the
  opponents' later play. The conversion to IMPs (3.6 a trick) is rough.
- The decisions are those of recorded 6-32 and 7s-32 games, not of the prototype's own games.
- The tree and the tie-break are left out; the prototype has both.
- The opponents are house bots and BEN as they played in the arena. A net reads a player whose
  carding it does not model worse than not reading (the Gen 8 session's `t-high` matches).
- One draw of the pool per decision (seeded by table and ply).

## Reproduce

```
python scripts/gen8_reading_bench.py pools  --episodes DIR [--episodes DIR ...] --skip-families TRAIN_SET.npz \
       --out OUT --shard 0/8 --net v0=... --net v2=... --net v4=... --net v4.1=... --net e5=...
python scripts/gen8_reading_bench.py owners --out OUT --episodes DIR --net ...
python scripts/gen8_reading_bench.py cards  --out OUT --episodes DIR
python scripts/gen8_reading_bench.py report --out OUT [--sweep | --owner 0.5 | --mechanism | --house | --against v4 --pairs-only]
```

About 50 seconds a table on one core with five nets. The stored pools and solves (530 tables) are
on azure5 under `~/work/p41/runs/reading`; a new net needs `fits` only, no solving. `pools.txt` is
the run's log. The interim figures posted at 08:08 UTC from the first 128 tables (v0 to v4.1
+0.022 +- 0.036) are superseded by this report.
