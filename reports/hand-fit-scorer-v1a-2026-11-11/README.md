# Hand-fit scorer v1a: retrained on the Gen 6 bidder's auctions (11 November 2026)

**Question.** Gen 6 weights its layouts after the opening lead with hand-fit scorer v0, which was
trained on auctions of the Gen 5 bidder. Every Gen 6 bot bids with the Gen 6 candidate bidder.
How much does retraining on that bidder's auctions help, and how far is a scorer from the exact
answer?

**Answer.** A little. Retrained with v0's recipe, v1a knows +0.040 ± 0.013 nats per decision more
about the true layout than v0 (log-scores × 1.5), about 12% of the 0.34-nat gap to the exact list.
No trick or IMP effect was measured. Further tests were judged not worth the effort; v1a is
released as a candidate for Gen 7: [models/cardplay/hand-fit-scorer-v1a-2026-11-11](../../models/cardplay/hand-fit-scorer-v1a-2026-11-11/README.md).
No arena bot uses it.

## Sources

- **Code:** `analysis/auction_belief/` on `research/joint-auction-belief-20261110` at `b13badd`,
  plus [`analysis-auction-belief.patch`](analysis-auction-belief.patch): `gen.py`, `gen_fit.py` and
  `verify_bidder.py` read the bidder path from `SDB_BIDDER`; `nbid.py` also reads BEN's base file,
  whose output layer has another name. The scripts here run against that code (`AUCTION_BELIEF`).
- **Bidders:** Gen 6 candidate `5b7ea255…`, Gen 5 `9ee52f3b…`, BEN base `b0dff3df…`, all from the
  feed's frozen `recovery` folder; each hash matches its release.
- **Test boards:** `arena-gen6-fast-selfplay-independent-feed` at `5ceafad`, episodes 000000–000399:
  370 Gen 6 self-play boards (`6-32~6-32`, 369 with a contract) and 30 `6-32~ben` boards. Root
  tables only; forks repeat them.
- **Check:** the NumPy bidder with the Gen 6 weights reproduces 150 of 150 recorded self-play
  auctions, all four seats (`verify_bidder.py`); with the Gen 5 weights, 112 of 150.

## Method

1. **Held-out hands** (`eval_scorer.py`): deals of seed 9 (v0's validation seed), bid once by each
   bidder; loss and accuracy on the true, random and near-miss hands.
2. **At the table** (`info_test.py`, `analyze_info.py`): at every decision in tricks 6–12 with at
   least two legal cards and at most 20,000 card-fit layouts (8,762 decisions), list every layout
   of the two hidden hands as the Gen 6 deal list does, weight them with the engine's `FitScorer`,
   and record log P(true layout). Information is that minus log P(true layout) under equal weights,
   in nats per decision. The yardstick is the exact list: equal weight on the layouts in which both
   hidden hands reproduce their seats' calls under the Gen 6 bidder, zero elsewhere. The true layout
   passes that check at all 8,762 decisions. Log-scores were also multiplied by 0.75, 1.25 and 1.5.
   Standard errors are clustered by board.

## Results

Held-out hands (`validation.txt`):

| Auctions bid by | Scorer | Loss | True hands right | Random | Near |
| --- | --- | --- | --- | --- | --- |
| Gen 6 bidder | v0 | 0.1378 | 90.7% | 96.3% | 93.6% |
| Gen 6 bidder | v1a | 0.1214 | 91.9% | 96.8% | 94.0% |
| Gen 5 bidder | v0 | 0.1115 | 92.2% | 97.2% | 94.5% |
| Gen 5 bidder | v1a | 0.1271 | 91.0% | 96.7% | 93.9% |

At the table, nats per decision (`info_summary.txt`, rows in `info_rows.jsonl.gz`):

| Trick | Decisions | Median layouts | v1a − v0 | v1a × 1.5 − v0 | Exact − v0 |
| --- | --- | --- | --- | --- | --- |
| 6 | 1,263 | 6,435 | +0.015 ± 0.017 | +0.046 ± 0.019 | +0.593 ± 0.035 |
| 7 | 1,275 | 924 | +0.026 ± 0.017 | +0.055 ± 0.018 | +0.538 ± 0.033 |
| 8 | 1,227 | 252 | +0.030 ± 0.017 | +0.053 ± 0.019 | +0.437 ± 0.029 |
| 9 | 1,265 | 70 | +0.022 ± 0.015 | +0.041 ± 0.016 | +0.359 ± 0.026 |
| 10 | 1,268 | 20 | +0.023 ± 0.012 | +0.037 ± 0.013 | +0.250 ± 0.021 |
| 11 | 1,232 | 6 | +0.015 ± 0.009 | +0.026 ± 0.009 | +0.146 ± 0.014 |
| 12 | 1,232 | 2 | +0.015 ± 0.007 | +0.022 ± 0.007 | +0.078 ± 0.010 |
| All | 8,762 | 70 | +0.021 ± 0.012 | +0.040 ± 0.013 | +0.344 ± 0.021 |

- Totals: exact 1.441 ± 0.035, v0 1.097 ± 0.032, v1a 1.118 ± 0.029, v1a × 1.5 1.137 ± 0.031.
- The factor 1.5 was chosen on the even episodes and scored on the odd ones, and the other way
  round; both halves chose 1.5. For v0 no factor helps: 1.0 and 1.25 tie and 1.5 is lower (a
  separate v0 run also tried 2 and 3, both lower: 1.064 and 0.984).
- For scale: on Gen 5 tables a 0.28-nat gap between v0 and the exact list was worth
  +0.025 ± 0.017 tricks per table (`reports/auction_belief_play_2026-11-11.md` on the research branch).

## Also measured

- **The exact list is cheap but not used** (`time_exact.py`, `timing_summary.txt`): 8.0 ms per
  decision on average (52 ms at trick 6, 0.9 s at most), 0.19 s per board for all four players
  against 0.10 s for the scorer, one core, verdicts cached per player and hand type. It needs the
  opponents' bidder, which a real table does not give, so it is not representative of real play.
  It stays a yardstick.
- **The arena's BEN bids as its base network does** (`ben_check.py`, `ben_check.txt`): on the 60
  native `6-32~ben` tables in the sample, the NumPy bidder with BEN's base weights reproduces all
  120 BEN seats' calls (and the Gen 6 bidder all 120 Gen 6 seats'). BEN's auctions can therefore be
  generated offline if a BEN-specific scorer or belief net is wanted.

## Limits

- Information about the layout, not tricks or IMPs; no arena play.
- Gen 6 self-play positions in tricks 6–12 only. Tricks 1–5 (hand-type classes) were not measured.
- Auctions of BEN, dds-40000 and other bidders were not measured; v1a is worse than v0 on Gen 5's.
- One training run, time-budgeted (22 minutes, 0.83 passes). Longer training, more data, other
  negatives and bidder mixes were not tested.
- The 1.5 factor needs a code change: the Gen 6 engine has no setting for it.
- The Gen 7 policy net's inputs are computed with the scorer (v0 for v0–v3.1).

## Reproduce

```bash
export SDB_FEED=/path/to/feed/recovery        # artifacts/, assets/, runtime/, episodes/
export AUCTION_BELIEF=/path/to/analysis/auction_belief   # research branch at b13badd, patch applied
(cd ../../models/cardplay/hand-fit-scorer-v1a-2026-11-11 && python restore.py)
SDB_BIDDER=$SDB_FEED/artifacts/gen6/bidder.keras python $AUCTION_BELIEF/gen_fit.py val9_gen6.npz 9 3000
SDB_BIDDER=$SDB_FEED/artifacts/v5/bidder.keras python $AUCTION_BELIEF/gen_fit.py val9_v5.npz 9 3000
python eval_scorer.py v0.npz v1a.npz -- val9_gen6.npz val9_v5.npz
python info_test.py --feed $SDB_FEED --bidder $SDB_FEED/artifacts/gen6/bidder.keras --out rows.jsonl \
    --scorers v0=v0.npz v1a=v1a.npz --first 0 --last 400 --alphas 0.75,1,1.25,1.5
python analyze_info.py rows.jsonl --base=v0 --by-trick
```

## Files

| File | What it is |
| --- | --- |
| `analysis-auction-belief.patch` | The change to the research branch's code |
| `eval_scorer.py`, `validation.txt` | Held-out loss and accuracy, and its output |
| `info_test.py`, `analyze_info.py` | The at-the-table test and its summary |
| `info_rows.jsonl.gz`, `info_summary.txt` | One row per decision (8,762), and the summary |
| `time_exact.py`, `timing_rows.jsonl.gz`, `timing_summary.txt` | Cost of the exact list against the scorer |
| `ben_check.py`, `ben_check.txt` | BEN's calls against its base network |
