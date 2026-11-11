# Hand-fit scorer v1a (11 November 2026)

**Status: research release. No arena bot uses it.** A candidate for Gen 7. Further testing was
judged not worth the effort: the measured gain over v0 is small (below).

v0's net and recipe, retrained on auctions of the bidder the Gen 6 bots actually use (the Gen 6
candidate, graded alternatives, SHA-256 `5b7ea255…`) instead of the Gen 5 bidder. Same
architecture, inputs and file layout as [v0](../hand-fit-scorer-v0-2026-11-11/README.md)
(1,435,393 parameters), so `bridge_harness.gen6_nets.FitScorer` loads it unchanged. Switching a
bot from v0 means changing its scorer file and hash, which makes it a new bot identity.

Run `python restore.py` here to rebuild `hand_fit_v1a.npz` (SHA-256 `875eb826…`) from its parts.

## Training

- **Data:** 460,387 random deals bid by the Gen 6 candidate bidder: `gen_fit.py` with seeds 3000
  and 3001, 230k deals each, about 17.5 minutes per seed on one core. As for v0, each seat
  contributes its true hand, 3 random hands and 5 hands with 1–8 cards swapped, each labelled by
  replaying that seat's calls greedily (16,573,932 examples). The NumPy bidder with these
  weights reproduces 150 of 150 recorded Gen 6 self-play auctions.
- **Recipe:** v0's, unchanged: `fit.py`, 22 minutes on two cores, 13,356 steps (0.83 passes).
  Log in `train_log.txt`.
- **Code:** `analysis/auction_belief/` on `research/joint-auction-belief-20261110` at `b13badd`,
  with the generator reading the bidder path from `SDB_BIDDER`
  ([patch](../../../reports/hand-fit-scorer-v1a-2026-11-11/analysis-auction-belief.patch)).

## Results

Held-out deals (seed 9, v0's validation seed; the same deals bid by each bidder):

| Auctions | Scorer | Loss | True hands right | Random | Near |
| --- | --- | --- | --- | --- | --- |
| Gen 6 bidder | v0 | 0.138 | 90.7% | 96.3% | 93.6% |
| Gen 6 bidder | **v1a** | **0.121** | 91.9% | 96.8% | 94.0% |
| Gen 5 bidder | v0 | 0.112 | 92.2% | 97.2% | 94.5% |
| Gen 5 bidder | v1a | 0.127 | 91.0% | 96.7% | 93.9% |

At the table: 369 Gen 6 self-play boards, 8,762 deal-list decisions in tricks 6–12. The figure is
how much the weighted list knows about the true layout beyond the cards and show-outs, in nats
per decision (standard errors clustered by board):

| Weights | Nats per decision |
| --- | --- |
| v0 | 1.097 ± 0.032 |
| v1a | 1.118 ± 0.029 |
| v1a, log-scores × 1.5 | 1.137 ± 0.031 |
| Exact list from the Gen 6 bidder (yardstick only) | 1.441 ± 0.035 |

- v1a over v0: +0.021 ± 0.012; with log-scores × 1.5, +0.040 ± 0.013. The factor 1.5 was chosen
  on half the boards and scored on the other half; both halves chose it.
- That closes about 12% of the 0.34 gap to the exact list. On Gen 5 tables a 0.28-nat gap
  between v0 and the exact list was worth +0.025 ± 0.017 tricks per table, so the trick value of
  v1a's gain is expected to be small. It was not measured.

Method, records and scripts: [reports/hand-fit-scorer-v1a-2026-11-11](../../../reports/hand-fit-scorer-v1a-2026-11-11/README.md).

## Before using it

- **The 1.5 factor needs a code change.** The Gen 6 engine has no setting for it; at factor 1 the
  gain is the +0.021 above.
- **The Gen 7 policy net reads the scorer.** Its `shown` inputs are computed with the scorer, and
  v0–v3.1 were trained with v0's (`scorer_sha256` `56e64440…` in their manifests). Using v1a there
  means retraining the policy net on v1a's readings, or keeping v0 for its inputs.
- **Other bidders:** v1a is worse than v0 on Gen 5 auctions. BEN's and dds-40000's auctions were
  not measured.
- **Not measured:** tricks or IMPs, tricks 1–5 (hand-type classes), any arena play.

## Reproduce

```bash
# analysis/auction_belief from research/joint-auction-belief-20261110 (b13badd), patch applied;
# SDB_FEED = a Gen 6 feed's recovery folder (artifacts/gen6/bidder.keras, runtime/)
export SDB_BIDDER=$SDB_FEED/artifacts/gen6/bidder.keras
OPENBLAS_NUM_THREADS=1 python gen_fit.py train_g6_3000.npz 3000 230000 &
OPENBLAS_NUM_THREADS=1 python gen_fit.py train_g6_3001.npz 3001 230000 &
wait
python gen_fit.py val9_gen6.npz 9 3000
OPENBLAS_NUM_THREADS=2 python fit.py v1a 22 val9_gen6.npz train_g6_3000.npz train_g6_3001.npz
```

The generated files' hashes are in `metrics.json`. Training is time-budgeted, so a run on other
hardware takes a different number of steps and will not reproduce the weights bit for bit.
