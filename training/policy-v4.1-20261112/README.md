# Policy net v4.1: the training run of 12 November 2026

**Status: a record of one run on a temporary machine. Work in progress while this note says so.**
The net is in [models/cardplay/gen7-policy-v4.1-2026-11-12](../../models/cardplay/gen7-policy-v4.1-2026-11-12/README.md),
with its scores. This folder has the scripts that made it and what else was run beside it.

Max's instructions (12 November, UTC): train a 4.1 net on everything collected so far, the Gen 7
boards included (03:32); a temporary fifth Azure box for it, at most two hours up (03:40); hold no
data back at all, because new boards arrive fast enough to test on (03:54); 512 wide first, then
768 wide and a head trained on fork results; report epoch by epoch (04:00); test whether the tree
becomes additive with the better net (04:54).

## What ran, in order

| Step | Script | Time on 8 cores |
| --- | --- | --- |
| Fetch every episode on `arena-gen6-*`, `arena-gen7-phase1-*` and `transfer/pre7-test-azure*`, one file per blob | `fetch_feeds.py` | 58 s for 38,207 episodes, 6.2 GB |
| Build the set in 16 parts and join them | `scripts/gen7_build_dataset.py`, `merge_sets.py` | 26 min; 38,128 boards, 13,239,367 examples |
| Held-out set B: what arrived since, minus deals the training set has | `fetch_feeds.py --seen`, `fresh_set.py` | 1 min; 631 boards |
| Train 512 wide on every deal | `scripts/train_gen7_policy.py --all-train --val-data` | 30 min (beside the 768-wide run) |
| Held-out set C, the same way, when that run ended | | 450 boards |
| Temperatures on B, the comparison on C | `evalnet.sh` | 5 min |

`chain.sh` is those steps as they ran on the box; `side.sh`, `after512.sh`, `after768.sh` and
`final_eval.sh` are the jobs that ran beside and after it. The manifests of the three fetches
(`fetch1.json`, `fetchB.json`, `fetchC.json`: every branch tip and count) and all logs are on branch
`transfer/gen7-policy-v4.1-box-20261112`, with every epoch's weights for both widths and the fork
pairs. The 10 GB training set is not kept; the first manifest and the builder reproduce it.

Changes to existing scripts: `scripts/train_gen7_policy.py` takes `--all-train` (train on every
deal of the set) and `--val-data` (held-out rows from a second set). Nothing else was changed.
New: `scripts/gen7_score_nets.py` (the trainer's per-epoch figures for any net on any set),
`scripts/gen7_pairs.py` and `scripts/gen7_result_head.py` (below).

## Still running when this was written

- The 768-wide run on the same data.
- The result head (experiment E2 on the fleet's queue): `scripts/gen7_pairs.py` lists every fork
  pair with the row of its decision in the set (722,589 pairs from the training boards: 169,601
  gap forks, 552,988 audits; the two cards' results differ in 12.9%). `scripts/gen7_result_head.py`
  fits one more decoder channel on those results with the net frozen and scores it on pairs from
  the fresh boards against the search's own gap.
- The tree bench on fresh fork pairs, v4's tree and v4.1's tree on the same pairs.

Their results will be added here.
