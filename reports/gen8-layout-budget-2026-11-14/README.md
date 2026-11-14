# Gen 8's early layout budget (14 November 2026)

Max's question (09:58 UTC): within Gen 8, what do more or fewer layouts buy or cost, in play and in training value?
Run by the stu-dash session in its own sandbox (2 cores, no box).

## Method

- **Positions.** 240 Gen 8 self-play tables (`scripts/gen8_match.py --pair g8a~g8b --one-room --common-only --episodes`,
  seed 9001, deals 900000 to 900239, loop branch `research/rollout-loop-20261113` at `f8cb58b`, capsule
  `arena-gen6-gen7-capture-feed` at `8833c62`). 12.9 CPU-seconds a table here. Records in `positions/`.
- **Decisions.** From each table, one non-forced decision in each of tricks 1-2, 3-4 and 5-6 (opening lead left out):
  720 in all. Only tricks 1 to 6 are replayed because from trick 7 Gen 8 lists every compatible layout (up to 256
  solved), and the budget does not apply there.
- **Budgets** (samples solved, pool drawn by the hand-fit scorer and weighted by the net's reading of the play): Gen 8's
  own 32 from 512, and 16, 64, 128, 256 from 512, and 128 and 256 from 2,048. The tree (tricks 3-6) and the net's
  tie-break run as in play. Budgets run in a shuffled order per decision.
- **Reference.** 1,024 layouts from a pool of 8,192, drawn the same way, every legal card solved double dummy, weighted
  as Gen 8 weights them. A decision's regret is the reference's best mean minus the reference mean of the chosen card,
  in the deciding side's tricks. Because the reference is Gen 8's own posterior and double dummy, this is the
  sampling-noise part of the budget's cost; it says nothing about whether the posterior or double dummy are right.
  Deliberate departures by the tree count as regret at every budget alike.
- **Per table.** Mean regret in each trick window times Gen 8's decisions a table in that window (6.3, 7.1 and 6.9 in
  tricks 1-2, 3-4 and 5-6, both sides). One bot's decisions over a duplicate board are about one table's, so a table's
  total reads as tricks a board for one bot. IMPs use the loop's conversion (0.07 tricks a board is about 0.1 IMPs).

## Results

| Budget | Regret a decision | Per table vs 32 (tricks) | ≈ IMPs a board vs 32 | Best card | Gap error | CPU a table vs 32 |
| --- | --- | --- | --- | --- | --- | --- |
| 16 from 512 | 0.0033 ± 0.0007 | +0.009 ± 0.017 | −0.013 ± 0.024 | 89% | 0.031 | −0.8 s (−6%) |
| **32 from 512 (Gen 8)** | 0.0028 ± 0.0006 | 0 | 0 | 90% | 0.021 | 0 |
| 64 from 512 | 0.0020 ± 0.0006 | −0.016 ± 0.013 | +0.023 ± 0.018 | 93% | 0.014 | +1.1 s (+9%) |
| 128 from 512 | 0.0018 ± 0.0005 | −0.021 ± 0.008 | +0.030 ± 0.012 | 92% | 0.011 | +3.2 s (+25%) |
| 128 from 2,048 | 0.0016 ± 0.0004 | −0.026 ± 0.009 | +0.037 ± 0.013 | 92% | 0.010 | +8.4 s (+65%) |
| 256 from 512 | 0.0015 ± 0.0004 | −0.028 ± 0.009 | +0.039 ± 0.013 | 93% | 0.010 | +8.9 s (+69%) |
| 256 from 2,048 | 0.0012 ± 0.0004 | −0.033 ± 0.010 | +0.048 ± 0.014 | 94% | 0.007 | +15.9 s (+123%) |

"Best card": share of decisions where the budget chose a card the reference rates best. "Gap error": mean absolute
error of the budget's per-card gap estimates (the gap head's labels) against the reference's, in tricks. CPU is process
time on this sandbox's cores, as a share of the 12.9 s table; the early decisions are 2.6 s (20%) of it at 32.

- At 32, sampling noise costs 0.058 tricks a table against unlimited layouts of Gen 8's own posterior, roughly 0.08
  IMPs a board. 256 from 2,048 removes about 60% of it.
- Most of the gain is in tricks 3-4, where the tree starts from the solved layouts (`summary.txt`, by window).
- 16 is within noise of 32 overall (worse in tricks 1-2 and 5-6, not in 3-4).
- The pool of 512 caps distinct layouts: 256 from 512 solves 169 distinct, 128 from 512 solves 103.

## Files

`gen8_budget.py` (the bench; `--root` is a checkout of the loop branch, `--source` the capsule's `recovery/`),
`summarize.py` (`summary.txt` and `summary.json` from `rows.jsonl`), `rows.jsonl` (one line per decision),
`decisions_per_table.json`, `positions/` (the 240 tables' records, results and summary).
