# The stored layouts and solves of the reading bench

Branch `transfer/gen8-p41-reading-pools-20261112` holds the `--out` folder of the run reported in
`reports/gen8-reading-by-net-2026-11-12/README.md` (branch `feature/gen8-p41-20261112`): 530
tables, 21,417 decisions, every layout solved once. The script is `scripts/gen8_reading_bench.py`
on that branch. A new reading
(another net, a signal model, an auction reader) can be scored on these decisions with no solving:
it only has to say how much log-weight it gives each stored layout and the true one.

Cards are numbers 0 to 51, `13 * suit + rank`, suits in the order S H D C, ranks 2 to A. Seats are
0 to 3 for N E S W.

## Files

A part holds up to four tables of one shard. Four files a part, the same decisions in the same
order in each:

`pools-SS-PPPP.npz`: flat arrays, one decision after another. Per decision `layouts` (L),
`unseen` (U) and `cards` (C) give the sizes.

| Array | Shape a decision | What |
| --- | --- | --- |
| `assign` | L x U, int8 | Each stored layout: which hidden seat, 0 or 1, holds each unseen card |
| `truth` | U, int8 | The same for the true deal |
| `u` | L x C, int8 | Double dummy in each layout, per legal card: the deciding side's final tricks, negated for the defence |
| `u_true` | C, int8 | The same on the true deal. A card's cost is `u_true.max() - u_true[card]` |
| `prior` | L, float32 | Log prior weight, normalised. Level before the deal list (the pool is drawn by the scorer's weights); the scorer's weights from the deal list on |
| `legal` | C, int8 | The legal cards, ascending: the columns of `u` |
| `fit:NET` | 3 x (L+1), float32 | The net's floored log-probability of the hidden seats' plays so far in each layout; the last column is the true deal. Rows: the opening lead, partner's other plays, the opponents' plays |
| `table`, `ply`, `trick` | scalars | Index into `tables`; index of the action in the root table; trick number |
| `regime` | scalar | 0: a pool before the deal list; 1: the deal list |
| `declaring`, `hidden_house` | scalars | The decider is on declarer's side; both hidden seats were played by house bots |
| `listed`, `plays`, `solve_seconds` | scalars | Layout classes (pool) or card-fit layouts (list) in all; hidden plays read; time to solve |
| `tables` | per part | JSON: episode file, feed directory, table key, deal family, each seat's bot |

`uns-SS-PPPP.npz`: `cards` (U a decision: the unseen cards, ascending, the columns of `assign`),
`hidden` (2 a decision: the seats that `assign`'s 0 and 1 stand for), `controller` and `actor`
(who decides, and whose card it is: they differ when declarer plays from dummy).

`own-SS-PPPP.npz`: `own:NET` (L+1 a decision), the owner head's log-probability of each layout
from the decider's view.

`scw-SS-PPPP.npz`: `scorer` (L+1 a decision), the hand-fit scorer's auction log-weight of each
stored layout and of the true deal, up to a constant per decision. These are the weights that drew
the pools. A complete deal list has them as its `prior`; a list of more than 1,024 layouts is
itself a draw by them, with the draw's shares as `prior`.

`tab-SS-PPPP.json.gz`: the part's tables again with `board` (hands, dealer, vulnerability,
auction, contract, declarer) and `played` (the root table's cards in order), so that a decision
can be replayed without the arena's episode files: play the first `ply` cards of `played`.

`pools-SS.log` is each shard's log.

## Scoring a reading

```python
import sys; sys.path.insert(0, 'scripts')
import numpy as np
from gen8_reading_bench import load, score, mean_se

rows, tables, nets = load('pools-00-0000.npz')
r = rows[0]
x = my_log_weight(r)                      # length L+1: each stored layout, then the true deal
fit = np.zeros((3, len(x)), np.float32); fit[0] = x
gain, engine_cost, every_cost, used, effective, expected, relevant = score(r, fit, power=1.)
none = score(r, np.zeros_like(fit), 0.)   # no reading, same decision
saved = none[1] - engine_cost             # tricks saved at this decision, the engine's way
```

`score` adds `power * fit.sum(0)` to the prior, applies the prototype's `early_min_effective`
rule before the deal list, and returns the true layout's gain in log-weight, the cost of the card
chosen the engine's way (32 layouts resampled, mean over eight offsets) and from every layout.
To put a reading on top of a net's, add `r['fit'][NET]` to `fit`. `report` does the same over all
decisions with deals as the unit of the standard errors; `mean_se(values, families)` is its
estimator, and a decision's deal is `r['family']`.

Every stored set of layouts is either drawn by the hand-fit scorer's auction weights or weighted
by them. So an auction reader that replaces the scorer is scored as a correction to it: `x = its own log-probability of each layout - scorer`, with `scorer` from the
`scw` file. A reader whose weights differ a lot from the scorer's leaves few effective layouts in a
pool of 512; `score` returns that number.
