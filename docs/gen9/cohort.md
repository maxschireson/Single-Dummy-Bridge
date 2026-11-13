# The Gen 9 cohort: launch plan

Prepared by dave (Gen 9), 13 November 2026, the way Gen 8's cohorts were prepared
([notice, launch steps](../gen8_candidate_2026-11-12.md)). **`round9-cohort.json` is open** (06:40 UTC, on g9's go at
06:16 citing Max's 03:47 instruction; the azure4 preflight passed at 06:02; g7 registers the feed, board 06:32).
`round9-cohort-ben.json` stays closed until BEN 64 answers a bidding request on azure4.

Goal (g9, 03:49 UTC, after Max at 03:47: "I would like to see it deployed. Can we accelerate?"): the Gen 9 bot in
the live arena on azure4, counted on the dashboard, by about 14:00 UTC.

## Plans and bots

| Plan | Pairs | Where |
| --- | --- | --- |
| [`round9-cohort.json`](../../configs/round9-cohort.json) | `9a-32~8s-32` 1, `9a-32~71s-32` 1, `9a-32~8p-32` 1 | azure4 |
| [`round9-cohort-ben.json`](../../configs/round9-cohort-ben.json) | `9a-32~ben64` 1 | a machine with BEN's servers |

| Bot | What it is | Identity (built from the capsule's `6-32`) |
| --- | --- | --- |
| `9a-32` | `8p-32` reading each partnership through its player model (`bridge_harness/gen9.py`), `exploration` 1.0 | `38b76a8b1542` |
| `8p-32` | the control: Gen 7.1 standard with the play read from trick 1 at exponent 1.0, policy v4.1 | `a6f6accbf114` |
| `8s-32` | the arena's Gen 8 | `269fdf1854f4` (the arena's) |
| `71s-32` | the arena's Gen 7.1 | `7b0f58b4c403` (the arena's) |
| `ben64` | the source run's BEN (64) | |

Choices made here (dave to g9, 13 Nov 04:40 UTC; open to change until the plan opens):

1. **Policy v4.1** for `9a-32` and `8p-32` (the arrival run used v4), so that `8p-32` is the arena's `8s-32` without
   the opponent table and the system scorer, and the cohort excludes v4.1's training families like every Gen 8 cohort.
2. **House bots are modelled as the house system** (`house-gen6`), as in the arrival run: the replay reader then
   reads their auctions after the opening lead. `9a-32` differed from `8p-32` by +0.19 +- 0.13 over 669 boards there.
3. **BEN has no model**, so `9a-32` reads BEN exactly as `8p-32` does (full weight, no opponent table, no system
   scorer), unlike `8s-32`, which reads BEN's plays at 0.5 and its calls by BEN's system file.
4. **No experience.** The live collector has no experience pipeline; the models are what each side declares.
5. **`exploration` 1.0**: a random one of its exactly equal-best cards (E9-16: +0.014 +- 0.126 against `8p-32`).

## Source

`feature/gen9-cohort`: PR #32's head (`a4858f53`, Gen 8 for main, which holds the collector code the Gen 8 cohorts
run: `systems`, `bidder`, `system_scorer`, `seat_table`), with `feature/gen9` and `feature/gen9-arena-arrival`
merged in (conflicts resolved toward the Gen 8 code), plus:

- `ops/gen5_runtime.py`: `engine: gen9` builds `bridge_harness.gen9.Gen9Player`.
- `ops/prepare_gen7_alpha.py`: a plan's bot entry may give `engine: gen9`, a `gen9` block (checked: known keys, readers
  that import, models that parse, no experience, never the test-only oracle) and `exploration`.
- `ops/smoke_gen7.py`: Gen 9 bots get the Gen 7 decision checks (they search as Gen 7 does).
- `scripts/gen9_match.py`: passes the table's systems through to the auction (PR #32's `gen5_arena.auction` takes them).

`bridge_harness/` (with `gen9.py` and the card readers) is in the manifest's `source_sha256`, so a collector refuses
a changed Gen 9 player.

## Steps

1. **Source**: a checkout of `feature/gen9-cohort` at the commit the preflight passed on.
2. **Artifacts**: `python models/cardplay/gen7-policy-v4.1-2026-11-12/restore.py` and
   `python models/cardplay/gen8-system-scorer-v1-2026-11-12/restore_model.py`.
3. **Prepare**, with fresh deals: azure4 has no drained run with deals no cohort was given (will's inventory,
   13 Nov 04:48 UTC), so the cohort takes fresh deals the way independent cohorts did
   (`ops/prepare_gen6_independent.py`), and the drained source run supplies only the bots and artifacts:
   `python ops/prepare_gen7_alpha.py --source <drained run> --run <run> --plan configs/round9-cohort.json --exclude-families v41-training-families-union.json --fresh N --fresh-seed S --played played-families-20261113.json.gz`.
   Left out: v4.1's training families (`transfer/v41-training-families-union-20261112`, `fccbbd8`, 34,092), every
   family of the source's corpus, and every family played on a registered feed at 04:26 UTC (85,910, from the
   ladder's collection; `transfer/gen9-cohort-inputs-20261113`). The manifest records the seed, the count and what was
   left out under `fresh_deals`, and is marked `independent_cohort`.
4. **Preflight**: `python ops/smoke_gen7.py --run <run> --out <report> --deals 2`. Done locally on 13 Nov at 05:05
   UTC (a synthetic drained source built from the capsule's bots, 60 fresh deals, seed 913, TensorFlow 2.21): the
   three pairs one deal each through the runtime path, no failure, the Gen 7 decision checks passed for `9a-32`
   (2,810 searched decisions, 267 tree consultations, none over budget), 66 to 92 seconds a deal in one process.
   **On azure4, 13 Nov 06:02 UTC** (job `g9-cohort-preflight`, `ops/preflight_gen9_cohort.py` at `007ff06d`, results on
   `transfer/gen9-g9-cohort-preflight-azure4-20261113`): prepared from `~/work/capsule-gen7-capture/recovery` in 4 s,
   manifest `351d25896a53`, 10,000 fresh deals (seed 9013; left out 34,092 training families, the capsule's 23,233
   deals and 85,910 played families); `9a-32` `38b76a8b1542`, `8p-32` `a6f6accbf114`, `8s-32` `269fdf1854f4`,
   `71s-32` `7b0f58b4c403`. Smoke: two deals of each pair, no assertion and no error, 66 to 114 seconds a deal in one
   process on a box running two other jobs; 417 tree consultations, none over budget.
5. **Open** the plan (`launch_enabled` true, `pending` empty, Max's words in `notes`) only after Max's go.
6. **Collector and feed**: on azure4 as one queue job, `ops/run_gen9_cohort.py` (prepares on first start, then the
   publisher every minute and the collector in the foreground; resumable; `STOP` in the run drains it). Tested end to
   end locally at 06:44 UTC: six fresh deals prepared, played by three workers and published to a local feed branch
   whose `recovery/` holds the runtime with `bridge_harness/cards/`. Underneath it are the runtime
   (`python ops/gen5_runtime.py --run <run> --workers N`) and the publisher (`python ops/publish_gen5.py --run <run>
   --publication <feed checkout>`), feed `arena-gen9-azure4-feed`, registration on the dashboard as g7 says. The
   publisher's runtime snapshot now copies `bridge_harness/` with its subpackages (the card readers are in
   `bridge_harness/cards/`), so a recovery from the feed can rebuild the frozen source. At about 85 seconds a deal in
   one process, eight workers play about 340 boards an hour: 10,000 deals last a little over a day.

## Known limits

- In the collector nobody calls `auction_by`, so `9a-32` attributes each side's calls to that side's model also in
  the common auction (bid by `6-32` at all four seats). Every house model here is `house-gen6`, the system `6-32`
  bids, so nothing changes in this roster; with BEN the common auction is read as BEN's (plain), as `8p-32` does.
- `tests/test_gen9_cards.py` fails five cases on this branch: bill's cards for the rule systems were written for the
  older rule bidder on `feature/gen9`, and PR #32 carries r4. No cohort bot bids or reads a rule system.
- The cohort measures `9a-32` against house bots and BEN, where its player model has little to add by design; its
  gain against declared-carding guests (+0.48 +- 0.13 in the arrival run) is not in this roster.
