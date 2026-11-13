# Stu dashboard

Live page: <https://maxschireson.github.io/Single-Dummy-Bridge/stu/> (deployed from this folder to `gh-pages:stu/`).

**Status: work in progress (13 November 2026).** Round 0 is the only generation so far; most cells read "not run"
until the validation matches below are played.

Stu is the rollout loop's bot (`training/rollout-loop-20261113/` on `research/rollout-loop-20261113`): each round's net
is trained on the previous Stu's self-play games, and the next Stu uses that net inside its rollouts. The arena page
compares recipes; this page follows one recipe round by round and asks three questions of every round:

1. **Is the net better?** Held-out log-loss, top-1 agreement, share of decisions with a best card first, and regret
   (tricks the net's top card gives up against the best searched card), with the previous net scored on the same rows
   where the trainer recorded it. Source: the training run's `metrics.json`.
2. **Does that reach the table, without and with amplification?** On fixed deals (seed 131, deal index from 0, the
   common bidder), against opponents the nets were never trained on, three players a round:

   | Role | Bot id (round *n*) | What it is |
   | --- | --- | --- |
   | Net alone | `n-stu<n>` | The round's net, top card at every trick. No search, no rollouts, no claims |
   | Net + rollouts | `r7-stu<n>` | The net's top card through trick 6, rollouts on the same net from trick 7. No search, no claims |
   | Stu | `stu<n>a` | The bot as it plays the loop (8Z's settings) |

   Amplification is Stu − net and rollouts − net, paired by deal. Change from the previous round is the same role's
   difference on the same deals. Leverage is the question whether the change in Stu tracks the change in the net.
3. **What is the round's data?** Self-play boards, CPU a board, rollout and blend decisions a board, and how often the
   rollouts changed the net's card (that should fall as the net improves).

New-against-old (`stu<n>a~stu<n-1>a`) is shown beside the gate, not as the verdict: the new net was trained on the old
bot's games, so it predicts that bot (see the leverage control in the round's README).

## What the page reads

- `registry.json` (this folder): the generations, each with its bot ids by role, old ids (`aliases`), the net's label,
  file and `metrics.json` location (`branch`, `path`, and `previous_compare`, the key under `compared` that holds the
  previous net on the same rows); the validation seed and opponents; the transfer branches to read.
- The loop's transfer branches (`transfer/rollout-loop-<box>-20261113`), as `pub.sh` publishes them every ten minutes:
  `runs.log` (one `start`/`end` line per job), and per run `results.jsonl` (one row a board), `summary.json`,
  `EPISODES.txt`.
- `data.json`: a snapshot of all of that reduced to a few numbers a board, written by `build.cjs`.

A run is classified by its pair and seed alone: both ids a round's Stu on a seed other than 131 is self-play; a round's
bot against a registry opponent on seed 131 is a validation cell; the same role of two rounds is new-against-old;
anything else is listed under other matches. Run names matching `exclude_runs` (preflights) are left out. One board
per deal family per cell; a run under a round's own ids counts before one under its old ids.

The page shows the snapshot and re-reads, every five minutes, every run that is still going or that changed after the
snapshot was built (raw GitHub files, cached up to five minutes by GitHub). Self-play runs are re-read by their
episode count only; their decision counters come from the snapshot.

## Adding a round

1. Add the generation to `registry.json`: `round`, `label`, `bots` (`stu`, `net`, `roll`), `net.metrics` and
   `net.previous_compare`. Bot ids must be unique across generations (a test checks).
2. Play the validation cells on seed 131 under those ids, e.g. `n-stu1~8p-32-v41`, `r7-stu1~8p-32-v41`,
   `stu1a~8p-32-v41`, and `stu1a~stu0a` for new against old. 2,000 deals a cell gives a standard error of about 0.05
   IMPs a board on paired differences.
3. If the round's runs publish to a new transfer branch, add it under `branches`.
4. `bash web/stu/publish.sh` rebuilds the snapshot and pushes `gh-pages:stu/`.

## Files

| File | What |
| --- | --- |
| `index.html` | The page |
| `stu-core.js` | Classification, per-run reduction, statistics, net scores; used by the page and by `build.cjs` |
| `build.cjs` | `node web/stu/build.cjs --repo <checkout> --out data.json`: fetches the branches (depth 1) and writes the snapshot |
| `publish.sh` | Builds the snapshot and pushes the page to `gh-pages:stu/`, retrying on a lost race |
| `registry.json` | Generations, roles, opponents, branches |
| `tests/` | `node --test web/stu/tests/stu-core.test.cjs`; fixtures cut from the loop's branches on 13 November |

## Limits

- IMP differences against the same opponent are not head-to-head IMPs; they rank players against a common yardstick.
- Net scores are only comparable across rounds on the same held-out rows; the page shows each round's held-out set
  and the previous net's score on that round's rows, where recorded.
- Self-play decision counters are as of the snapshot. Rates are not shown: rows carry no timestamps.
- "Rollouts changed the card" counts, for the rollout stage, a card outside the net's likeliest candidate, and for the
  blend stage, a card off the search's best (`scripts/x8_match.py`, `summarise_actions`).
