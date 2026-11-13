# Rollout net v2 (13 November 2026)

**Status: work in progress, research only. No bot uses it.** Max, 13 November (UTC): give every opponent an id and
include them all, don't exclude for the sake of it (00:11); start from v4.1's full data; the best policy recipe was
768 wide with the rate falling over 5 epochs (00:11, 00:25). Runs on azure2 after rollout net v1
([../rollout-net-v1-20261113](../rollout-net-v1-20261113/README.md)), as queue job `rnet2`.

## Against the policy net (v4.1, and its 768-wide 5-epoch run)

Same: the net (`suit` kind) and its inputs, the four targets (card played, the search's gap for each legal card, holder
of each unseen card, final tricks) and their loss weights, the schedule (fresh run, rate 2e-3 warmed up and falling by
one cosine to 1/50 over all five epochs, batch 512, AdamW, weight decay 1e-4), and the held-out rows: every deal of the
set is trained on and the held-out boards are those that reached the feeds after the fetch, minus deals the set has.

Different:

| | v4.1 | v2 |
| --- | --- | --- |
| Episodes | the feeds at 03:59 UTC on 12 November (`arena-gen6-*`, `arena-gen7-phase1-*`, `transfer/pre7-test-azure*`): 38,128 boards | the same patterns now, plus every `arena-gen7-*` and `arena-gen8-*` feed (v1's fetch and what it lacks) |
| Decisions | the searched ones only (Gen 6's and Gen 7's search) | every decision with more than one legal card: BEN, Gen 5, Gen 1-3, the Gen 7 net's own cards too |
| Who plays | not an input: one average player, weighted by how many decisions each bot made | two learned vectors, the deciding side's bot and the other side's, added to the first trunk layer; 15% of training rows read each as unknown, so that row is a generic player |
| Gap target | every row | rows with the search's gap only (`has_gap`); the others train the card, owner and tricks heads |
| Width | 512 (v4.1); 768 in the 5-epoch run | 768 |
| Scores | by trick phase and side | also by bot, from trick 7, with the ids blanked (`who_use`), v4.1 and v1's nets on the same rows (`compared`), a temperature per epoch |

Still the policy net's limit: the target is the card the bot played. Targets better than the bot (its probabilities
over level cards, values from inside playouts, the claim finder's per-card guarantees) are not in v2.

## What `chain.sh` does (expected times on the 8 cores)

1. Fetch what v1's fetch (`$P/rnet1/eps`) lacks from the four patterns above: about 35,000 episodes (61,383 episode
   paths on 111 branches at 01:10 UTC).
2. Build the set from both directories in 16 parts with `scripts/gen7_build_dataset.py --policy-only` and join them with
   `merge_sets.py` (renumbers the bots into one `bot_names`): about an hour; roughly 25 to 35 million rows.
3. Held out: fetch again (what arrived during step 2), build, and drop deals the set has (`fresh_set.py`).
4. `scripts/train_rollout_net.py --all-train --val-data freshB.npz --kind suit --width 768 --epochs 5 --save-epochs`,
   scored against v4.1 and v1's two nets: about two hours (v4.1's 768x5 run took 46 minutes for 13.2 million rows).
5. Push `runs/w768` (every epoch, metrics) and the logs to `transfer/rollout-net-v2-20261113`.

A toy run (`LIMIT=15 WIDTH=128 EPOCHS=1 SHARDS=2 NOPUSH=1`) passed in the sandbox at 01:12 UTC.

## Using it

`bridge_harness.gen7_net.PolicyNet` reads a net with `bot_vocab`; set `net.who = (own bot name, other side's bot name)`
before `log_policy` or `heads` (a name it was not trained on reads as unknown). Nets without `bot_vocab` are unchanged.

## Changes to existing scripts

- `scripts/gen7_build_dataset.py`: `--policy-only`; `meta` columns 8 and 9 are now the deciding side's and the other
  side's bot as rows of the set's own `bot_names` ('' at row 0), column 10 `has_gap` (v1 numbered column 8 from a
  fixed list).
- `bridge_harness/gen7_net.py`: optional bot vectors (`emb_own`, `emb_other`) and `PolicyNet.who`.
- New: `scripts/train_rollout_net.py` (from the v4.1 run's trainer on `transfer/gen7-policy-v4.1-20261112`, with its
  `--all-train`, `--val-data`, `--save-epochs`, `--init`).
