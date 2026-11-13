# Rollout net v1 (13 November 2026)

**Status: work in progress, research only. No bot uses it.** Max, 12 November 23:39 and 23:52 UTC: build a net for
playouts, trained on the matches of Gen 7 and later, on one of the plan session's Azure boxes. Background:
[the plan-leverage report](../../reports/plan-leverage-2026-11-12/README.md), sections 2, 5 and 7: inside a playout
the net stands in for the bot at every seat, and how well it reproduces the bot sets what the playouts are worth.

## What `chain.sh` does

| Step | What | Expected time on 8 cores |
| --- | --- | --- |
| Fetch | every episode on the 82 Gen 7 and Gen 8 feeds of the dashboard registry (`feeds.txt`, gh-pages `arena/gen6-sources.json` at 23:45 UTC on 12 November), with `fetch_feeds.py` (copied from `training/policy-v4.1-20261112`) | minutes |
| Build | `scripts/gen7_build_dataset.py --bots 7s-32,7f-32,71s-32,8s-32,8c-32`: the searched decisions of the Gen 7+ bots only; opponents' cards (BEN, Gen 6, Gen 5, Gen 1) are left out | about 20 minutes |
| `ft` | v4.1's weights fine-tuned on that set, 4 epochs, learning rate 5e-4 | about 10 minutes |
| `scratch` | the same net from random weights, 6 epochs, 2e-3 | about 15 minutes |
| Score | each net and v4.1 on the held-out deals (family hash: 10% validation, which picks the epoch, and 10% test), by trick and by bot | in the training runs |

Targets as in v4.1: the card the bot played (policy head), the search's gap for every legal card (gap head), the holder
of each unseen card and the final tricks. About two thirds of the Gen 7+ cards are searched decisions; the rest are
the net's own choices or single legal cards and are not in the set.

Comparing with v4.1: v4.1 trained on every deal on the feeds at 03:59 UTC on 12 November, Gen 7 phase 1 boards
included, so held-out rows of those deals are not held out for v4.1. The Gen 8 feeds hold no v4.1 training deal
(p41, board, 22:46 UTC), so the `8s-32` and `8c-32` rows of `by_bot` are the clean comparison.

## Not yet done

- Fidelity as a playout seat: does a playout with this net at every seat come out where the bot's own playout would,
  layout by layout (the share-reproduced measure of the report's section 2)? To run on the ceiling sets.
- Distortion: the true deal's rank under the net's reading of the play, and the same inside playouts.
- Soft targets from the bot's probabilities over its level cards, and positions taken from inside playouts.

Changes to existing scripts: `scripts/gen7_build_dataset.py` takes `--bots` and records the bot's name
(`meta` column 8, `bot_names`); `scripts/train_gen7_policy.py` takes `--init` (start from a net), `--compare` (score
other nets on the same rows) and reports `from_trick_7` and `by_bot`.
