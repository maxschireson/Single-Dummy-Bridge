> Historical README from the Gen6 source lineage before repository reorganization. Its original baseline descriptions and appended experiment updates are not current deployment authority. See [current system](../current-system.md).

# Bridge harness 0.1

The **DDS-only bidding self-improvement loop** is described in
[docs/dds_bidding_loop.md](../../docs/dds_bidding_loop.md). It fine-tunes the external
BEN bidder on paired duplicate IMP rewards without playing cards, with cached
DDS tables, optimizer checkpoints, a frozen league and held-out promotion gates.

A working baseline for single-dummy bridge experiments: legal play, simple players,
paired comparisons, saved deals, deterministic local decisions, and replay.
The goal of this version is to make an improvement measurable. Playing strength is
deliberately modest.

This branch adds **batch PIMC and self-play training data**. See
[self-play usage and training schema](../../docs/SELFPLAY.md) and
[the measured first-run report](../../reports/selfplay_initial_2026-11-08.md).
The [updated training plan](../../docs/TRAINING_PLAN.md) covers small bidding-aware belief
models, independent evaluation data, and BEN-bid/PIMC-play collection.

```sh
python3 scripts/build_dds.py
python3 -m bridge_harness.selfplay --count 1000 --workers 8 --samples 32 \
  --near-tie 0.125 --out data/first_selfplay
```

## Design and roadmap

The [self-improvement loop runbook](../../docs/SELF_IMPROVEMENT.md) describes the
resumable 10k → 50k → 250k self-play/training ladder, immutable bot registry,
paired IMP arena against original/parent/BEN, and controlled v3/v4 promotion.
It is staged for the finalized v2 factory/weights/trainer; no production loop
is launched automatically. See `configs/self_improvement.json` for the recipe.

The [version 4 design document (PDF)](../../docs/Single_Dummy_Machine_v4.pdf) describes
the target hybrid bot, self-play learning, the research league and independent
arena, and the staged path from this harness. It also records the alpha-mu
strategy-search and related-deal solver-reuse work in progress.

An [editable Word version](../../docs/Single_Dummy_Machine_v4.docx) is included.

The [PIMC research checkpoint, 8 November 2026](../../reports/pimc_findings_and_next_steps_2026-11-08.md)
records the alpha-mu and rollout experiments, the 1,000-board quality/cost results,
small-ending partitions, and the next belief-model and learned-selector experiments.
The experimental source is preserved separately on
[`research/pimc-study-2026-11-08`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/pimc-study-2026-11-08).

## Start on a Mac or Linux machine

Requires Python 3.11+ and a C++20 compiler. On a Mac, install Apple's command-line
developer tools if needed (`xcode-select --install`). The Python harness has no
third-party dependencies. DDS source and its Apache 2.0 license are included.

From the extracted project directory:

```sh
python3 scripts/build_dds.py
python3 -m unittest discover -s tests -v
python3 -m bridge_harness generate --count 1000 --seed 20261108 \
  --out corpora/broad_1000.jsonl
python3 -m bridge_harness generate --count 1000 --family-size 100 --seed 20261109 \
  --out corpora/related_1000.jsonl
python3 -m bridge_harness match corpora/broad_1000.jsonl \
  --candidate pimc --baseline greedy --samples 32 --limit 20 \
  --out my_results/first_match.jsonl
python3 -m bridge_harness replay my_results/first_match.jsonl
```

Each match writes JSONL decision records plus a Markdown report and JSON summary.
For `first_match.jsonl`, the summaries are `first_match.md` and `first_match.json`.
Use a new output filename for each experiment. `--resume` continues an interrupted
run with exactly the same corpus and settings, skipping all recorded boards,
including failures. A killed partial board is rerun; completed records are flushed
after every pair. Do not run two writers against the same output file.

Without DDS, `random` and `greedy` still run. DDS compilation uses up to four CPU
threads. Matches are serial, with each paired board in its own worker process.

## Players and information

| Player | Behavior |
|---|---|
| `random` | Uniform random legal card; useful as a smoke baseline. |
| `greedy` | Tries to win the current trick cheaply, avoids overtaking partner, leads a high card. Deliberately weak. |
| `pimc` | Samples hidden hands consistent with hard public information; asks DDS to score every legal card in each sampled world; maximizes average utility. Default 32 samples. |
| `ben` | Calls a separately running BEN engine through `/lead` and `/play`; `/bid` supplies frozen auctions. |

Only the runner owns all four actual hands. Players receive an immutable
`Observation`: their own hand, exposed dummy, public auction/play, contract,
vulnerability, and legal actions. Dummy's actions are controlled by declarer.
Before the opening lead, dummy is concealed. Neither actual hidden hands nor the
deal-generation seed is passed to a player. This is an API boundary for trusted
research players, not a security sandbox for hostile Python code.

The sampler is uniform over deals satisfying remaining card counts and observed
voids. It uses exact combinatorial completion counts when void constraints apply.
It does **not** use auction likelihoods, opponent skill, signals, or likelihoods of
earlier card choices. This is the intended first baseline, not a belief network.

PIMC assumes perfect-information continuations inside each sampled world. It can
choose incompatible future lines across worlds (strategy fusion). It does not yet
search information-consistent contingent strategies. DDS values are converted
from the acting partnership's remaining tricks to declarer's final trick total
before scoring. `--objective score` maximizes expected duplicate score; alternatives
are `tricks` and `make`. IMPs are used to report paired results, not as an assumed
oracle at each decision. Forced moves skip sampling and DDS.

## Comparison modes

```sh
# Candidate declares; both tables use the same common defenders and fixed lead.
python3 -m bridge_harness match corpora/broad_1000.jsonl \
  --mode declarer --candidate pimc --baseline greedy --common greedy \
  --samples 32 --out my_results/declarer.jsonl

# Candidate defends; both tables use the same common declarer and fixed lead.
python3 -m bridge_harness match corpora/related_1000.jsonl \
  --mode defence --candidate pimc --baseline greedy --common greedy \
  --samples 32 --out my_results/defence.jsonl

# Table 1: candidate NS, baseline EW. Table 2: baseline NS, candidate EW.
python3 -m bridge_harness match corpora/broad_1000.jsonl \
  --mode partnership --candidate pimc --baseline random --samples 8 \
  --out my_results/partnership.jsonl
```

`declarer` and `defence` compare continuation play. If a corpus has no opening
lead, `common` selects one once for both tables. Defence mode therefore does not
measure the candidate's opening-lead strength. Partnership mode includes each
player's own opening lead unless one is explicitly frozen in the corpus. In all
modes, defenders respond to the actual evolving history; later cards are never
forced to match a different trajectory.

Positive IMPs favor the candidate. In partnership mode, the difference is table
1's NS score minus table 2's NS score. The other modes orient the score to the
candidate's role. Reports include mean IMPs, wins/ties/losses, timing, DDS calls,
largest discrepancies, and failures. Uncertainty uses a 2,000-resample cluster
bootstrap, treating related deals with the same `family` as one cluster. With only
ten families, inference remains limited. Reported intervals exclude failed pairs
and cannot correct corpus bias or engine mismatches.

`--board-timeout 300` is a hard deadline for the two-table worker, including native
solver calls. `--timeout 120` limits a BEN HTTP request. Illegal actions, engine
errors, crashes, and timeouts are recorded; no substitute player silently finishes
the board. Actions received before a worker timeout are retained. A deadline can
kill the local client; it cannot cancel work already accepted by a remote server.

## Corpora, auctions and PBN

Generate the corpora with the commands above; bulk data is excluded from Git.
These seeds reproduce the original broad and related JSONL corpora exactly:

- `broad_1000.jsonl`: 1,000 distinct deals, all strains, declarer directions and
  vulnerability combinations. Contracts and auctions are synthetic scaffolding.
- `related_1000.jsonl`: ten families of 100 layouts; N/S are fixed within each
  family, E/W are resampled, South declares. Contracts and metadata remain fixed
  within each family. This is useful for future reuse experiments.
- The small live integration set has auctions generated by BEN. Run
  `scripts/ben_integration.py` to produce a new set; BEN output may vary with
  its runtime and models. This is not a strength benchmark.

The synthetic corpora are reliability and profiling workloads, not a calibrated
population of tournament contracts. In particular, giving synthetic auctions to a
bid-aware engine can distort its beliefs. Freeze real engine auctions or import
curated deals for meaningful playing-strength comparisons.

```sh
python3 -m bridge_harness generate --count 1000 --seed 42 --out my_deals.jsonl
python3 -m bridge_harness generate --count 1000 --family-size 1000 \
  --seed 43 --out one_related_family.jsonl
python3 -m bridge_harness convert my_deals.jsonl my_deals.pbn
python3 -m bridge_harness convert my_deals.pbn imported.jsonl
```

JSONL preserves all harness metadata. PBN import/export supports complete deals,
dealer, vulnerability, auction, contract, declarer, and optional `OpeningLead` and
`Family` extension tags. It is a practical subset of PBN, not a full PBN editor:
partial deals, claims, results/play import, and inherited tag values are unsupported.
Use unique Board IDs. Original imported auctions must agree with the contract.

## BEN: real external-engine integration

The adapter was checked against BEN commit
`9b5f43104aeac713a80b73513f2f2d6daf9f8769` (API version 0.9.0.2).
BEN's source and original large model files remain external to this package.
The user-adopted 40k DDS fine-tune is published separately under
[models/bidding/dds-40000](../../models/bidding/dds-40000), with upstream attribution
and license.

```sh
git clone https://github.com/lorserker/ben.git ../ben
git -C ../ben checkout 9b5f43104aeac713a80b73513f2f2d6daf9f8769
python3 -m venv ../ben-venv
../ben-venv/bin/python -m pip install -r ../ben/requirements.txt

python3 scripts/ben_integration.py --ben-dir ../ben \
  --ben-python ../ben-venv/bin/python --out my_results/ben_check
```

The integration script starts BEN, freezes four complete auctions using only the
current bidder's hand per request, then plays eight complete table games with PIMC
and BEN swapping partnerships. It stops the server afterward. It writes the exact
BEN config and revision alongside the records. It disables BBA, BGA PIMC, ACE and
SuitC extensions to use BEN's portable neural/DDS path. That configuration must be
named when interpreting results; it does not stand for every BEN setup.

For larger calibration runs, `scripts/ben_integration.py` accepts `--count`,
`--deal-seed`, `--decision-seed`, `--samples`, `--objective`, `--near-tie`, and
`--resume`. Defaults for our player are batch PIMC, 32 worlds, expected tricks,
and uniform selection within 0.125 estimated tricks. BEN defaults to two DDS
threads to bound parallel server resource use; its search sample counts are
unchanged. Resume checks saved deals, BEN configuration and match settings and
preserves completed auctions/games. Match reports include candidate-oriented
paired tricks as well as IMPs, with uncertainty clustered by deal/family.

With your own BEN server already running:

```sh
python3 -m bridge_harness freeze-auctions my_deals.jsonl frozen.jsonl \
  --ben-url http://127.0.0.1:8085
python3 -m bridge_harness match frozen.jsonl --mode partnership \
  --candidate pimc --baseline ben --samples 32 --board-timeout 600 \
  --ben-label 'my BEN revision and config' --out my_results/vs_ben.jsonl
```

The adapter uses original 13-card hands, chronological played cards, absolute
vulnerability, and declarer's seat when playing dummy. It never sends the whole
deal to `/bid`, `/lead`, or `/play`. Logged requests/responses allow inspection.
Local players are deterministic under recorded seeds/configuration. BEN response
reproducibility additionally depends on its build, model weights, config and
runtime; recorded-action replay does not require rerunning BEN.

## Inspect and branch a deal

```sh
python3 -m bridge_harness replay my_results/first_match.jsonl --board 7
python3 -m bridge_harness branch my_results/first_match.jsonl --board 7 \
  --table 0 --player pimc --out my_results/board7_branch.jsonl
```

Branching defaults to just before the first differing decision between tables.
Use `--ply 12` for an explicit zero-based decision. The selected actor's partnership
gets the replacement player; previous cards are replayed, and all subsequent
players respond to the resulting history. A branch is one table, not a paired
match, so it can be replayed but is not input for the paired summary command.
Branch execution currently uses the calling process (HTTP timeout still applies;
the match command's hard process deadline does not).

## Files and extension points

| Module | Responsibility |
|---|---|
| `core.py` | Cards, auction validation, scoring, rules, information boundary |
| `sampling.py` | Exact uniform constrained hidden-hand sampler |
| `dds.py` | ctypes binding; one persistent native context per player/worker |
| `players.py` | Random, greedy, PIMC and BEN; `choose(observation, rng)` interface |
| `runner.py` | Paired matches, subprocess deadlines, action recording, replay |
| `corpus.py` | Generation, frozen auctions, JSONL/PBN |
| `report.py` | Paired IMPs, cluster uncertainty, timings and discrepancies |

Batch PIMC now retains native DDS proofs across the sampled worlds of one
decision. Self play collects policy outcomes, PIMC values, behavior probabilities
and hidden-hand labels with whole-deal splits. Model fitting, learned sampling,
learned play selection, an endgame database and opponent-skill inference are not
implemented. See `docs/SELFPLAY.md` for the next experiments and their limits.

See `VALIDATION.md` for the actual runs and their limits.

## Source upload

This repository includes source, tests, the required DDS sources, licenses,
reproduction scripts, and compact historical reports in `reports/`. Bulk deal
corpora, per-decision JSONL records, generated JSON summaries, server/test logs,
compiled binaries, and model weights are excluded. The original experiment
archive remains unchanged. See `CREDITS.md` for attribution.


The 10,000 independent complete self-play deals passed the cross-shard audit.
See [completed collection](../../reports/selfplay_initial_2026-11-08.md) and the
[small-model training plan](../../docs/TRAINING_PLAN.md). The optional
`scripts/train_belief.py` fits an observation-only ownership baseline; real
auction training needs additional BEN data, and bot strength is evaluated
separately from supervised validation metrics.

[First training results](../../reports/first_belief_training_2026-11-08.md): two small
fits completed; neither beat the ownership prior on validation.

[Fast bidding and auction-belief results](../../reports/fast_bidding_and_belief_2026-11-08.md):
50,000 independent auctions collected; a 46,582-parameter model improved
validation ownership predictions. Playing strength has not yet been measured.

## Bidding-informed sampling experiment

The [frozen-model evaluation](../../reports/bidding_sampling_2026-11-08.md) compares
auction-weighted and uniform PIMC at 32 worlds, measures card ownership after
dummy appears, and separates declarer and defensive effects. Experimental
inference needs NumPy; the default PIMC sampler is unchanged.
