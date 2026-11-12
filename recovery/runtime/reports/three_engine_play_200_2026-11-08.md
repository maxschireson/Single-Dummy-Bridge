# Baseline, bidding-informed PIMC, and BEN on identical deals

8 November 2026. **Status: running; no completed 200-deal BEN result yet.**

The existing bidding-informed comparison measured +0.180 tricks per paired
deal (95% deal-bootstrap interval +0.05 to +0.32), and +0.535 IMPs
(-0.045 to +1.095), over 200 independent deals. Those games compared two
32-world PIMC players and did not include BEN card play.

This extension adds BEN to the exact same 200 deals, preserving the original
hands, dealer, vulnerability, completed auction, contract and declarer. It
reuses the existing 400 informed-versus-uniform games, and adds 800 games:

| Matchup | Independent deals | Games per deal | Status at launch |
|---|---:|---:|---|
| Bidding-informed PIMC vs uniform PIMC | 200 | 2 | Complete, reused |
| BEN vs uniform PIMC | 200 | 2 | Running |
| BEN vs bidding-informed PIMC | 200 | 2 | Running |

Each matchup swaps the engines' NS/EW partnerships between tables. Every
engine therefore declares and defends the same contract. Opening leads are
chosen by the relevant engine. Positive trick and IMP swings favor the first
engine named. A paired trick swing combines declaring and defensive effects;
it is not extra declarer tricks when both partnerships use the same engine.

## Engine settings

- Both PIMC variants use batch DDS, 32 legal sampled worlds per non-forced
  decision, expected-tricks utility, and uniform choice among moves within
  0.125 estimated tricks. The informed sampler adds the frozen 46,582-parameter
  auction model at weight strength 1.0, with exact capacity/void conditioning.
- BEN uses the same portable neural/DDS configuration as the separate full
  BEN calibration: `play_nn_only=False`, configured 200 play samples, bidding
  inference, IMP-oriented decisions, and two DDS threads. BBA, BGA PIMC, ACE
  and SuitC remain disabled. No search setting has been reduced.
- BEN revision: `9b5f43104aeac713a80b73513f2f2d6daf9f8769`.
- BEN config SHA256:
  `960d3b316967f22ed5c251a94b8e6714a249cc1851a02f193cc1f15e8f1dbfab`.
- Frozen auction weights SHA256:
  `c070981c21cc79eed2205b5dbe6693e5804641a05d7ce32948df10bf15a1e96a`.
- Original evaluation corpus SHA256:
  `1c70375e97b77bb2152c97a374a4ffdda751adbfe41e24a6bdc6b2287e92d0fd`.
- Parent published engine source:
  `143d88161782cf35b382c203bb3eddce33d4a728`; every Python engine file used
  here matches that published version. The runner and audit tests are new.

This measures the engines as configured, including their differing objectives
and compute budgets. It is not an equal-time strength comparison. Decision
times are recorded separately. BEN uses the already-frozen neural auctions;
no full-search bidding is repeated. Results apply to that auction population.

## Why the previous BEN result cannot fill in the missing cells

A snapshot of the first 23 completed pairs in the separate BEN calibration
showed BEN ahead of baseline by 0.435 tricks per paired deal, with a 95%
bootstrap interval [-0.043, +0.913], and 2.043 IMPs [-0.174, +4.478].
These are incomplete, provisional results from different deals and full-search
auctions. The earlier four-deal integration used only eight PIMC samples and
is also unsuitable for this comparison. Neither estimate can be combined
with the +0.180 result to infer a measured BEN-versus-informed gap.

Even on a shared corpus, all three head-to-head matchups should be measured:
the gains need not be exactly transitive because opposing play changes the
information and decisions encountered.

## Reporting and validation

The protocol fixes all 200 deal hashes before any new BEN outcome. There is
no outcome-dependent stopping, tuning, or replacement of failed deals. The
population has already been inspected in the original frozen-model test;
it is not a fresh post-tuning holdout.

The runner checks source, native solver, weight, original record and config
hashes; independently replays cards and scores; verifies both partnership
assignments and 32-world budgets; and audits every BEN request against the
public observation. Hidden hands are never sent. Completed tables and pairs
are saved atomically and reused on resume. Failures are retained for inspection.

The evolving summary distinguishes the original full-200 result from results
on the common subset for which both new BEN matchups have completed. Its three
head-to-head rows always use identical deal hashes. Confidence intervals
resample deals, not tables, moves or hidden-card labels. An interim common
subset remains incomplete and must not be presented as the planned final test.

Five existing weighted-sampling tests and three new audit tests passed. The
new tests check NS/EW score orientation, hidden dummy exclusion at opening
lead, changed context/budget rejection, and score validation. All 400 original
games passed legal replay before launch.

## Reproduction and continuation

The original experiment archive is `Bridge_Bidding_Sampling_Evaluation_2026-11-08.zip`.
Its `results/` directory supplies the source run, including the original
200-deal corpus, model weights and completed paired records. BEN source/models
remain external and are not redistributed.

```bash
python3 scripts/evaluate_three_engines.py prepare \
  --source-run results/bidding-sampling-original \
  --out results/three-engine-200 \
  --ben-dir /path/to/ben --ben-config /path/to/calibration/ben.conf

OPENBLAS_NUM_THREADS=1 python3 -u scripts/evaluate_three_engines.py run \
  --out results/three-engine-200 --ben-dir /path/to/ben \
  --ben-python /path/to/ben-venv/bin/python --port 8891

python3 scripts/evaluate_three_engines.py report --out results/three-engine-200
```

Resume with the identical `run` command. A worker lock prevents duplicate
invocations from writing the same games. Inspect a recorded failure before
archiving that attempt and deliberately retrying it. Do not overwrite failures
or replace an engine. The separate full-search BEN calibration is unchanged.

Max Schireson directed this comparison. OpenAI ChatGPT/Codex implemented the
runner and audit. The experiment builds on DDS and BEN and their contributors;
see `CREDITS.md` for source attribution and licensing.
