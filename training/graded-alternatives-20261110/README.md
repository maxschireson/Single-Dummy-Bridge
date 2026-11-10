# Graded-alternatives bidding experiment — 10 Nov 2026

Status: experiment result, not promoted. Max named it the candidate Gen 6 bidder "when the time comes".
Every number is double-dummy scored; card play is untested.

Question: on the same 40,000 solved deals used for the PPO-40k bidder, does grading every plausible
alternative call (instead of sampling one line per deal, as PPO does) train a better bidder?

## Method

- Start from the BEN base (`GIB-BBO-8742_2026-10-23-E30.keras`, sha256 `b0dff3df…`).
- Training deals: the first 35,000 of the uploaded 40,000. Held out here: the last 5,000 plus the 1,000
  development deals (never trained on by these nets; PPO-40k did train on or select with them).
- For each chunk of 2,500 deals, both rooms are bid greedily (learner pair vs frozen base pair). At every
  learner decision, each non-greedy call with probability >= 1% (at most 4) is played instead and the
  auction is finished greedily. Its label is the IMP difference against the greedy line, from the deal's
  cached double-dummy table. 15% of decisions without an alternative are kept for the anchor term.
- Loss per decision: `-(sum_k p(alt_k) * adv_k) / 10 + 0.02 * KL(base || learner)`. Same optimiser settings
  as `bidding_ppo.PPO` (Adam, global-norm clip 0.5, BatchNorm frozen, dropout off). Minibatch 128, 2 epochs
  per chunk, each deal used once per pass.
- Evaluation: greedy duplicate, both rooms, double-dummy score, IMPs per deal; same as
  `scripts/review_bidding_snapshot.py`. The fast simulator in `abid.py` was checked against the harness
  (`selfcheck.py`: 630 decisions, 0 feature, legal-mask or score mismatches; 128 of 128 auctions identical)
  and reproduces the PPO-40k review exactly (+313 IMPs, 172 W / 156 L / 4,672 T).

## Results (all measured; IMPs per board, +- one standard error)

Review deals (seed 2326250810, split `test`, indices 0-4999):

| Net | vs base | head-to-head vs PPO-40k |
| --- | --- | --- |
| PPO-40k | +0.063 +- 0.029 | |
| graded, lr 1e-5, 1 pass | +0.119 +- 0.036 | +0.050 +- 0.030 |
| graded, lr 1e-5, 2 passes | +0.166 +- 0.041 | +0.099 +- 0.036 |
| graded, lr 3e-5, 1 pass | +0.209 +- 0.044 | +0.152 +- 0.040 |
| graded, lr 3e-5, 2 passes | +0.293 +- 0.049 | +0.217 +- 0.046 |
| graded, lr 1e-4, 1 pass | +0.291 +- 0.056 | +0.206 +- 0.053 |

New test deals (seed 1911102026, split `test`, indices 0-2269; first evaluated after the lr 3e-5 runs were finished,
then once more for the lr 1e-4 net):

| Net | vs base | head-to-head vs PPO-40k |
| --- | --- | --- |
| PPO-40k | +0.069 +- 0.044 | |
| graded, lr 3e-5, 1 pass | +0.248 +- 0.067 | +0.183 +- 0.060 |
| graded, lr 3e-5, 2 passes | +0.398 +- 0.075 | +0.327 +- 0.069 |
| graded, lr 1e-4, 1 pass | +0.382 +- 0.086 | +0.308 +- 0.084 |

Review and new deals pooled (7,270 deals): lr 3e-5 two passes +0.326 +- 0.041 vs base and +0.251 +- 0.038 vs PPO-40k;
PPO-40k +0.065 +- 0.024 vs base. lr 1e-4 one pass against lr 3e-5 two passes head-to-head: +0.027 +- 0.042 (review),
+0.015 +- 0.068 (new deals). The lr 1e-4 run hit the per-chunk KL stop (0.02) in 9 of 14 chunks.

Against the current Gen 5 bidder (`play50_anchor002`, sha256 `9ee52f3b…`), lr 3e-5 two passes head-to-head:
+0.213 +- 0.046 on the review deals (507 W / 367 L / 4,126 T), +0.331 +- 0.068 on the new deals, +0.250 +- 0.038 pooled.
The Gen 5 bidder itself: +0.069 +- 0.028 vs base and +0.004 +- 0.008 vs PPO-40k on the review deals
(it differs from PPO-40k on 26 of the 5,000 boards).

Held-out 6,000 (last 5,000 training deals + development set), vs base: lr 1e-5 one pass +0.151 +- 0.034,
two passes +0.222 +- 0.038; lr 3e-5 one pass +0.269 +- 0.040, two passes +0.337 +- 0.045; lr 1e-4 one pass +0.367 +- 0.051;
PPO-40k +0.123 +- 0.027 (in-sample for PPO-40k).

In-sample check (first 10,000 training deals, vs base): lr 3e-5 one pass +0.547 +- 0.033,
lr 1e-5 two passes +0.464 +- 0.031, PPO-40k +0.126 +- 0.021.

Cost here: 6.5-9 minutes per pass over 35,000 deals on 2 CPU cores, given the tables.

## Where the gain comes from (lr 3e-5 two passes; 11,000 held-out deals x 2 seatings)

Contracts the net's side declares that base-vs-base did not reach: 1,971, worth +2,443 IMPs as bid;
52% make double-dummy; if an opponent doubled every one of them the total would be +5,001 IMPs.
Largest groups: a higher class of contract (part-score to game, game to slam) 715 contracts, +1,316 IMPs,
51% make; declaring instead of defending or passing out 640, +809 IMPs, 35% make.

## Not tested

- Real card play. Every number above is double-dummy.
- Opponents that adapt. The opponent in training and evaluation is the frozen base (or PPO-40k).
- More than two passes, and fresh deals for each pass.

## Files

- `restore.py` + `manifest.json`: `python training/graded-alternatives-20261110/restore.py --out /tmp/graded-alternatives`
  verifies every checksum and rebuilds the two bidders from the 256 KiB chunks in `models/` (standard library only).
- `graded_lr3e5_2pass.keras` (sha256 `5b7ea255…`): the net to test. The lr 1e-4 net scores the same and
  changes more boards; it is not included (`python3 train_a.py --tag a_lr1e4 --lr 1e-4` rebuilds it).
- `graded_lr3e5_1pass.keras` (sha256 `864ce2e7…`): one pass over the deals, like PPO-40k.
  Both load with `bridge_harness.bidding_ppo.Policy.load`. They are fine-tuned BEN weights; `models/BEN-LICENSE.txt` applies.
- `data/new_test_seed1911102026.jsonl.gz`: 2,270 new solved deals in the export schema
  (`index, family, hands, dealer, vulnerability, dds`). `make_board(1911102026, index, 'test')` regenerates them.
- `scripts/abid.py`: vectorised auction simulator, duplicate scorer and alternative grader.
- `scripts/train_a.py`: the training loop. `scripts/evalnets.py`: comparisons. `scripts/diag.py`, `scripts/stress.py`:
  the breakdowns above. `scripts/solve_tables.py`: resumable double-dummy solving with the harness solver.
  `scripts/selfcheck.py`: simulator-vs-harness check.
- `logs/*.jsonl.gz`: per-chunk training logs and held-out evaluations.

The scripts have two hard-coded paths: `/home/claude/gen5r` (a checkout of the repository with
`bridge_harness/libbridge_dds.so` built) and `/home/claude/bid` (this folder, with `base.keras`, `ppo40k.keras`
and `data/train.jsonl.gz`, `data/dev.jsonl.gz` restored from `transfer/dds-bidding-40000-20261110`).

## Reproduce

```bash
python3 train_a.py --tag a_lr3e5 --lr 3e-5
python3 train_a.py --tag a_lr3e5_p2 --lr 3e-5 --init runs/a_lr3e5/final.keras --seed 2
python3 solve_tables.py 2326250810 test 0 5000 data/review_test.jsonl 2
python3 evalnets.py review base=base.keras ppo=ppo40k.keras a=runs/a_lr3e5_p2/final.keras -- a:base ppo:base a:ppo
```
