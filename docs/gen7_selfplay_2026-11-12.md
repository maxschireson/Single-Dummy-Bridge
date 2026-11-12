# Gen 7: the Gen 5 and Gen 1 pairs stop, their deals go to self-play. Notice for the collectors (12 November 2026)

**Status: authorized by Max, 12 November 2026, 04:09 UTC.** "We can stop collecting on 5 and on
1; it's clear enough. Put those deals toward self play." For the team controlling the workers.
Branch `feature/gen7-selfplay-20261112`, cut from `main` at `62bd8a2`; use commit `7780e5e` or
later. Not merged to `main`.

This page says what the instruction changes for a collector and what code it needs. Like the
[phase 1 notice](gen7_candidate_2026-11-11.md), it stops and starts no collector: which collectors
move, and when, is Max's instruction to each of them. The BEN pairs are unchanged. Phase 2
(`configs/round7-candidate-phase2.json`, with the fast bot's self-play) stays closed.

## Where the two pairs stood

All collectors together, raw counts, 04:15 UTC:

| Pair | Boards | IMPs a board for `7s-32` |
| --- | ---: | --- |
| `7s-32~5RZ32` | 1,218 | +1.11 +- 0.12 |
| `7s-32~1` | 1,217 | +2.19 +- 0.13 |

Their records and feeds stay as they are. A cohort that schedules them cannot drop them (a plan
has no per-pair switch), so it is drained and a new cohort takes over the deals it had not played.

## The plan

`configs/round7-phase1-selfplay.json` is the non-BEN phase 1 plan with the Gen 5 and Gen 1 pairs
replaced by `7s-32` against itself, weight for weight:

| Pair | Weight | What a board is |
| --- | ---: | --- |
| `7s-32~6-32` | 1 | Two tables on one deal, common and native auctions, as in phase 1 |
| `7s-32~7s-32` | 2 | One table: `7s-32` in all four seats, the common bidder's auction, no swapped room |

The bot, the policy release, the common bidder and the audit reference are those of phase 1, so
`7s-32` keeps its identity (`f0a57859...` on the capture capsule). Self-play supplies training data.
Its records carry the regime `self` with a null score difference and null IMPs, never zeros; the
feed counts the boards and shows no IMP figure for the pair.

## The code

Before this branch no source had both the Gen 7 engine and a collector that accepts a bot playing
itself ([backlog](backlog.md), item 1). `bridge_harness/gen5_arena.py` on `main` already played
such a pair; the collector refused its record.

| Commit | Adds | Gap forks and guess-size fields recorded |
| --- | --- | --- |
| `05d2cd8` | `ops/gen5_runtime.py` checks and receipts a `self` record; `ops/export_gen5.py` writes its null differences; the plan; tests. The checks are those of the Gen 6 self-play collector (`codex/gen6-fast-selfplay-20261111`, `a8ae688`), unchanged | no |
| `199337d`, `81707b2` | `ops/prepare_gen7_alpha.py` accepts a drained Gen 7 cohort as the source run: the bots are kept, and a plan whose Gen 7 bot has the same id with other settings is refused | no |
| `7780e5e` | Merges the capture port, `codex/gen7-phase1-independent-20261112` at `522eda6` (gap forks, `guess_size`, `best_share`, `--actor-source`) | **yes** |

**Capture.** A cohort inherits `audit` and `gap_fork` from its source run. The launch source
`fe382f9` and `main` carry `gap_fork` without acting on it, so records made from them have tie
audits and tree audits but no gap forks: that is every Azure phase 1, pre-arena test and BEN lane
record, the Codex phase 1 records, and any self-play cohort prepared before `7780e5e`. The
independent collector's records (source `522eda6`) have 11 to 23 gap forks a board. Since self-play
is collected for training, prepare self-play cohorts from `7780e5e` or later. A cohort's manifest
names its source commit.

The plan file differs between these commits in its notes only (three versions); pair weights and
the bot are the same in all.

## Switching a collector

1. Drain the phase 1 cohort: write `STOP`, wait for the collector to finish its boards and for the
   feed to publish the last of them. Keep the run folder.
2. Check out `7780e5e` or later in a **new** directory (the old cohort's checkout stays where it
   is), restore the model releases, build DDS, and run `python -m unittest discover -s tests -p
   "test_gen7*.py"` and `-p test_gap_forks.py`.
3. Prepare the new cohort from the drained one, so that exactly the deals it had not played are
   used and none is played twice in the Gen 6 matchup:
   `python ops/prepare_gen7_alpha.py --source OLD_RUN --run NEW_RUN --plan configs/round7-phase1-selfplay.json`.
   The source needs `STOP` and `WATCHDOG_STOP` and no failure records, and is then finished for
   good. A machine with no phase 1 cohort prepares from the capture capsule with its own
   `--shard K/N` instead. A deal already played in another matchup may be used for self-play.
4. Preflight: `python ops/smoke_gen7.py --run NEW_RUN --out NEW_RUN/preflight.json`. It plays two
   deals of each pair, the self-play pair included, through the real runtime path.
5. Start `python ops/gen5_runtime.py --run NEW_RUN --workers W` and publish with
   `ops/publish_gen5.py` to a new feed branch. The pairs have no BEN, so every worker is a normal
   one. Add the feed to the dashboard registry.
6. A plan has no per-pair target. To end the Gen 6 comparison, drain the cohort and prepare its
   successor from a copy of the plan that keeps the self-play pair; the roster must still name two
   bots, because the runtime's schedule needs two.

## Who has switched

As of 04:56 UTC. Check fresh feed heads before relying on a row.

| Producer | State |
| --- | --- |
| Codex | First cohort prepared at `05d2cd8` from its phase 1 cohort (32 boards, no gap forks; feed `arena-gen7-selfplay-codex-20261112-feed`), then a successor with capture: feed `arena-gen7-selfplay-capture-codex-20261112-feed` |
| Cloud | Phase 1 cohort drained at 67 boards; shard 4/8 kept for its self-play successor; waiting for this branch |
| azure2 | Cohort `c50412d34108` prepared at `7780e5e` from the box's phase 1 deals (2,202); 11 trial boards, then stopped; feed `arena-gen7-phase1-selfplay-azure2-feed`, registered. The box plays the BEN (16) pair until that reaches 2,000 boards, then this cohort with eight workers |
| azure1, azure3, azure4 | Phase 1 cohorts stopped (828, 720 and 829 boards). azure3 is on the BEN (64) pair, azure1 and azure4 on Gen 8 experiments; their unplayed phase 1 deals wait |
| Independent | Registered a self-play feed with capture at 04:51 (`gen7independentselfplay` in the registry) |
| Extra | No change seen |

## What was tested

On `azure2` (Azure Standard_F8as_v6) with DDS and TensorFlow, at `7780e5e`, while the box was
also playing the BEN (16) lanes:

- `test_gen7*.py` 62 tests, `test_gap_forks.py` 11, `test_gen[56]*.py` 41: all pass.
  `tests/test_gen7_selfplay.py` (7 of them, toy players) covers the record of a bot playing itself,
  the refusal of a self-play record with a score or the wrong tables, a cohort that mixes both
  pairs, the plan against the phase 1 plan, a self-play table with gap forks, and preparation from a
  capsule-like source and from a drained Gen 7 cohort.
- Preflight of cohort `c50412d34108` (the box's 2,202 unplayed phase 1 deals) passed in 210 s:

  | Deal | Pair | Seconds | Tables | Searched decisions | Tree consulted, moved | Gap forks |
  | --- | --- | ---: | ---: | ---: | --- | ---: |
  | 0 | `7s-32~7s-32` | 62 | 1 | 469 | 56, 3 | 6 |
  | 1 | `7s-32~6-32` | 63 | 2 | 346 | 24, 1 | 12 |
  | 2 | `7s-32~7s-32` | 51 | 1 | 538 | 46, 8 | 6 |
  | 3 | `7s-32~6-32` | 30 | 2 | 227 | 17, 0 | 11 |

- A trial of that cohort through `ops/gen5_runtime.py` with two workers: 11 boards in 412 s, no
  failures, published by `ops/publish_gen5.py`; the dashboard's checks pass on the feed.

  | Pair | Boards | CPU seconds a board | Audit forks a board | Gap forks a board |
  | --- | ---: | ---: | ---: | ---: |
  | `7s-32~7s-32` | 8 | 33 | 58 | 5.8 |
  | `7s-32~6-32` | 3 | 47 | 31 | 11.7 |

Before the capture merge, at `81707b2`:

- Preflight passed in 124 s; the two self-play boards took 35 s and 23 s without gap forks.
- A first cohort played 4 boards (2 of each pair) through `ops/gen5_runtime.py` with two workers
  and `ops/publish_gen5.py` published them: `transfer/gen7-selfplay-trial-azure2-20261112`. The
  dashboard's own loader checks and rollup (`verify` and `build` in `arena/reporting.js` on
  `gh-pages`), run on that feed's files, accept it: the self-play pair is counted with null totals
  and no wins, ties or losses; the Gen 6 pair is scored as before. The cohort above took over that
  cohort's unplayed deals.

Not tested: eight workers at volume, a long run, a resume after a stop.

## Not done

- **Fast self-play (`7f-32~7f-32`).** The same runtime would accept it; there is no open plan with
  it and it was not run.
- **A stop for one pair inside a cohort.** See step 6.
- **Speed.** The Gen 8 session found that eight workers sharing one `dds-cache.sqlite` wait on its
  writes, and that turning the cache off raised a fork-free match from 1,056 to 1,267 boards an hour
  on one box. `ops/gen5_runtime.py` always sets a cache for the run. Not tried here.
- **Merge to `main`.** This branch is `main` plus the capture port plus self-play; the other
  collector code named in the backlog's item 1 (feed-health supervision, BEN auto-expansion) is not
  in it.
