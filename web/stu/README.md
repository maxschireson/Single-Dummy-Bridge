# Stu dashboard

Live page: <https://maxschireson.github.io/Single-Dummy-Bridge/stu/> (deployed from this folder to `gh-pages:stu/`).

**Status: work in progress (13 November 2026).** Three boxes collect pure Stu's self-play overnight; rounds 1 and 2 are
scored; round 3 trains at about 07:00 UTC on 14 November.

Stu is the rollout loop's bot (`training/rollout-loop-20261113/` on `research/rollout-loop-20261113`): each round's net
is trained on the previous Stu's games, and the next Stu plays with that net inside its rollouts. The arena page compares
recipes; this page follows one recipe round by round. The loop session's brief for it is
`training/rollout-loop-20261113/DASHBOARD.md` on that branch: what each run is, what to compute, and what not to read
into the numbers.

## What it shows

| Section | What | Source |
| --- | --- | --- |
| Now running | Per box (azure3, azure5, azure6): the jobs in hand (side by side when started together), done, rate, time left for matches; the collection's tables by box and in all | `runs.log` (a pause line stops a box's collection), `<run>.log` progress lines |
| Round by round | The collection (rate, boards by the bot that played them), and each round's own net alone, inside Stu's own stages and inside pure Stu (the main line from 11:25 UTC) against Gen 8 card play on every seed-131 deal played (0 to 1,999), with the change from the previous round paired by deal; the net's held-out log-loss (Stu's own rows from round 1); the decision mix and how often rollouts changed the net's card or lead | runs `collection`, `gate`, `ladder` (`registry.round_rungs`) |
| The ladder | Every rung (where rollouts take over) by net, against Gen 8 card play on the deals its ladder runs plan (0 to 499, or 0 to 999 for Stu's own stages and pure Stu with v2); each rung minus its reference rung (`ref`: Stu's own stages, or pure Stu for the two lead variants), and each net minus the one before it, paired by deal | runs `ladder` |
| The fusion ledger | Per bot (net and rung) and for Gen 8 card play pooled: declaring cards that gave up a held guarantee, defending cards that handed one over, by contract class | `ledger/ledger.json` on azure3's transfer branch (`fusion_ledger.py`) |
| Leverage | For consecutive nets: the change in held-out log-loss and regret on the same rows, beside the change in IMPs at each rung. The `net` rung (the net alone, no search, no rollouts) is the unamplified measurement | trainer `metrics.json` (`compared`), ladder |
| The nets | Held-out scores, the earlier nets on the same rows, training curves | trainer `metrics.json` |
| Collections | Per run: boards, rate, failures, CPU, decision mix, the self-play IMPs check, a stall flag | runs `collection`, `<run>.log` |
| Against BEN (64) | Each bot against BEN on seed 131 deals 0 to 255 (card play only), minus Gen 8 card play's result against BEN by deal, beside the bot's own result against Gen 8 on those deals | runs `ben` (eight `folders` each, one `results.jsonl` a folder) |
| The leverage control | The 2 by 2 of the round README, and its split into "inside net matches the opponent" and "better net inside" | runs `control`, else the sandbox's 300 deals |
| Health | Each box's heartbeat age, load, memory, disk; when its rows were last published | `box/<box>/status:heartbeat.json`, GitHub commits API |

## How it reads the data

- `registry.json` (this folder): the rounds (net, the round's cut), the nets (label, `metrics.json` location, and
  `compare`: the keys under `compared` that hold earlier nets scored on this net's rows), the rungs in display order, the
  opponent, the control's cells, the boxes and their branches, cautions.
- The loop's `runs.json` says what each run is (role, round, net, rung, whether it is still in a job file, `passes`),
  and per round any collection cut (`rounds`). A run it does not list is shown under other matches; preflights are left
  out; a run it no longer lists is read by the bot ids it does list (marked superseded). A job that ends at the end of a
  pass short of the planned deals shows as "pass done". Collection rows with one table a board (`common: null`) count
  as boards, CPU and decisions, not IMPs.
- A net can name `before` files: the same held-out rows scored by an earlier net, for an earlier net that `compared`
  misreads (round 1: v2 reads Stu as an unknown bot under `compared`; `train-r1/metrics_before.json` tells it Stu is
  `8s-32`). `focus_bot` (round 1: `stu0`) adds that bot's rows from `by_bot` beside all rows.
- The boxes' transfer branches (`transfer/rollout-loop-<box>-20261113`): `runs.log`, and per run `results.jsonl`,
  `<run>.log`, `EPISODES.txt`, published about every ten minutes.
- `data.json`: a snapshot reduced to a few numbers a board, written by `build.cjs` with the same code the page uses.
  The page shows it, then every five minutes re-reads the run list, the heartbeats and every run that is running or
  changed after the snapshot. Collections are re-read by their counts only; their decision counters come from the
  snapshot.

A cell keeps one board per deal family. Boards of a superseded run (the same bot under an earlier id or job) count only
where a current run has not played that deal, and the page says how many there are. Paired differences use the deal
families both cells played.

## Adding a round

1. In `registry.json`: add the round (`round`, `label`, `net`, `trained_on`, `main_rung`; `pending` until its net exists)
   and its net (`key` as `runs.json` names it, `metrics`, `before` and `focus_bot` where the trainer wrote them,
   `compare`). Colour: `slot` 1 to 3, each used once (validated against the page's surface with every pair
   distinguishable); give a new net the slot of the oldest loop net and set that one to `"ref"` (a grey ring).
   A variant of a round's net (`variant: true`) is shown with the nets but is not a step of the loop.
2. The loop session adds the round's runs to its job files and `runs.json`; nothing else is needed here.
3. `bash web/stu/publish.sh` rebuilds the snapshot and pushes `gh-pages:stu/`.

## Files

| File | What |
| --- | --- |
| `index.html` | The page |
| `stu-core.js` | Parsing, classification, per-run reduction, statistics, net scores, the model the page draws; used by the page and by `build.cjs` |
| `build.cjs` | `node web/stu/build.cjs --repo <checkout> --out data.json`: fetches the branches (depth 1) and writes the snapshot |
| `publish.sh` | Builds the snapshot and pushes the page to `gh-pages:stu/`, redoing a push that loses a race |
| `registry.json` | Rounds, nets, rungs, opponent, control, boxes, cautions |
| `tests/` | `node --test web/stu/tests/stu-core.test.cjs`; fixtures cut from the loop's branches on 13 November |

## Limits

- One outside opponent (Gen 8 card play). IMP differences against it rank players against a common yardstick; they are
  not head-to-head IMPs.
- Net scores compare across nets only on shared rows (the `compare` keys); the trainer reports no interval for them.
- Boards an hour is each run's own average since it started (its log's progress line), not the last hour's rate.
- The stall flag needs the page open, or reopened in the same browser, across 20 minutes.
- No four colours from the palette pass the all-pairs check on this surface, so at most three nets are coloured.
- A run counts as running when its last `runs.log` line is a start within 90 s of the box's latest start, with no
  pause line after it; jobs started side by side by other means would show as not running.
- "Rollouts changed the card" follows `scripts/x8_match.py`: rollout decisions whose card is not the table net's first
  choice, over rollout decisions.
