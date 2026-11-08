# Self-improvement loop

The processes are implemented on `research/self-improvement-loop`. No production
self-play, network fitting, BEN match, recurring task, or paid job was started as
part of setting this up. Finalize v2, bind its weights and trainer, then launch.

The controller supports frozen bot factories, so the remaining v2 policy work
can land without changing the experiment protocol. The supplied reference
trainer **only updates the existing auction belief model**. It is not a claim
that a policy network has been completed or that self-play already improves it.

## Experiment

1. Freeze v1 (original uniform PIMC), finalized v2, the bidder, and full-search
   BEN, including model/config hashes and search settings.
2. Generate 10,000 independent deals with genuine frozen auctions and have v2
   play all four seats. Train/select a candidate using train/validation only.
3. Compare candidate versus parent, original, and BEN on fresh independent
   deals. Also play the parent versus BEN on those **same** deals.
4. Promote only when both the head-to-head improvement over the parent and the
   improvement in performance against BEN pass the predeclared statistical gate.
5. Otherwise extend the same generation to 50,000, then 250,000 total deals.
   These require 40,000 and 200,000 additional deals, not three separate corpora.
6. If all three fail, retain the parent and stop for review. If promoted, label
   the accepted candidate v3, preserve every older version, and optionally start
   the next generation from v3 with fresh data. One generation per invocation is
   the default; `--generations N` explicitly bounds a longer run.

“Improvement against BEN” means
`IMPs(candidate vs BEN) - IMPs(parent vs BEN)` on each identical deal.
A candidate can improve against BEN while still losing to BEN overall.
This is not the same statistic as its head-to-head score versus its parent.

All comparisons swap partnerships at two tables. Positive IMPs favor the first
named engine. Auctions, contracts, vulnerability, deals, and the BEN reference
remain fixed within a comparison. Opening leads are chosen by each engine.
This measures **card play including opening leads**, with bidding frozen; it is
not a comparison of the bots' bidding strength. Passed-out deals remain in the
population as zero-IMP boards and are counted separately in training summaries.

## Size, uncertainty, and promotion

Training size and evaluation size are independent controls. Default training
stages are 10k/50k/250k; evaluation looks are 2k/8k/32k independent deals for each
candidate as provisional defaults. Size the arena for the desired effect, not
as a fixed 10% of training data. Halving the target gain approximately quadruples
the required number of independent evaluation deals. `size-arena` computes an
approximate plan from prior-pilot standard deviations of the two paired IMP
endpoints, including the actual BEN difference (not separate unpaired scores).
It accounts for the promotion alpha budget and targets 80% joint power by
conservatively splitting the power shortfall between endpoints. Freeze the final
evaluation sizes before looking at candidate arena outcomes; its estimate is not
a guarantee. Example with **illustrative**, not yet measured, standard deviations:

```sh
python3 -m bridge_harness.improvement size-arena \
  --effect 0.10 --sd-parent 2.0 --sd-ben-delta 3.0
```

The evaluation population grows cumulatively within one candidate;
different candidates and generations get new evaluation deals. A clearly losing
candidate can stop early; an inconclusive one gets the next evaluation look.

No size is promised to be sufficient. Training split proportions remain the
existing deal-hash 80/10/10 split: 10k self-play deals yield approximately 8k fit,
1k validation, and 1k unused internal test deals, not 520k independent examples.
All card decisions from one deal stay together. Passed-out deals have no policy
decisions. More data can reduce variance without fixing weak targets or a model
that cannot represent the information needed.

The primary endpoints are IMP/board versus parent and the paired BEN improvement.
Promotion needs the lower confidence bound of **both** to exceed
`minimum_imp_gain` (default zero). The controller allocates family alpha 0.05
across data stages, evaluation looks, both endpoints, and generations. Generation
g receives `0.05 / [g(g+1)]`, whose infinite sum is 0.05. The gate uses two-sided
Student-t intervals with this conservative allocation. These are approximate
large-sample intervals over independent deals, not exact anytime confidence
sequences. All-tie/zero-variance results cannot promote. A fresh campaign is a
new statistical family; repeatedly restarting campaigns is not a way to retain
the same global error budget.

The original/BEN absolute columns also show descriptive 95% intervals; those
intervals are not the promotion test. Raw rows, adjusted intervals, trick swings,
and match time are retained. No single scalar chess-style rating is assumed:
nontransitive matchups are possible. Evaluation reports are as-configured with
the parent's search budget fixed for candidate training; they do not claim
equal wall-clock strength. The added inference cost remains visible.

32k evaluation deals can be expensive: up to four distinct paired comparisons
means eight table games per independent deal, many involving full-search BEN.
The ladder is configurable **before** initializing the campaign. It is a cap,
not an estimate of affordable runtime. The existing 200-deal BEN calibration is
still useful to select a sensible fixed BEN setup and estimate this cost.

## Reproducibility and restart

- Bot names are immutable. Registry entries copy artifacts, hash code and native
  DDS, and record exact factory arguments. All accepted and rejected candidates
  remain available. A promotion atomically updates the champion and version
  history in one state file; failed candidates never replace the parent.
  If fitting selects exactly unchanged behavior/weights, the expensive arena is
  skipped and the controller advances to the next data stage.
- The campaign uses one pinned code/solver checkout for weight-only iterations.
  Source changes require a new campaign, preserving the old one for reproduction.
  `pinned_files` additionally hashes external training/bidding dependencies.
- Self-play uses 250-deal auction chunks and individually atomic compressed game
  records. Successful games are replay-validated on resume; they are not played
  again. Cumulative datasets reuse earlier shard identities. Training restarts a
  deterministic interrupted fit, but does not discard completed game collection.
- A SQLite ledger rejects duplicate cards and any self-play/arena overlap.
  Independent deals only are accepted; related-layout families are rejected by
  this initial arena. Optional exclusion lists reserve old v2 training/test IDs.
- A single OS-owned lock prevents competing writers and releases on process
  death. Workers are bounded and each table pair has a hard subprocess deadline.
  A failed/illegal/timed-out game blocks its candidate; failures are not silently
  dropped. `--retry-failures` explicitly retries the same deals/seeds, preserving
  failed records. Repeated instability should be fixed, not selected away.
- Genuine auctions are generated once and retained. A killed auction collector
  restarts only its incomplete 250-deal chunk, with prior partial output archived.
  The neural bidder can differ from full-search BEN's card-play configuration;
  both remain fixed and separately identified.
- Players receive the existing observation API, not hidden hands. Training inputs
  must use observation fields only; labels are attached after replay. Actual
  logged action probabilities/returns support policy learning. An unplayed action
  has no observed return; cloning chosen moves is not evidence of improvement.
  The trusted trainer API is not an operating-system security sandbox.

## Bind final v2 and launch

Use a stable persistent checkout/run directory on the eventual worker machine.
The current implementation stores absolute paths, so resuming after moving a
campaign requires preserving its mount paths. Archive the run directory together
with its pinned checkout and external model/config files.

```sh
python3 scripts/build_dds.py
python3 -m pip install -e '.[loop]'
python3 -m unittest discover -s tests -v
cp configs/self_improvement.json /path/to/experiment.json
```

The template intentionally contains unbound paths and null commands. It must not
silently run an unfinished v2. Fill:

- `bots.v2`: the final factory, inference arguments, search budget, and all
  belief/policy artifact paths. The example uses the already-existing auction
  weighting adapter; replace the factory if v2 includes the pending policy.
- `trainer_command`: argv for the finalized learner. It receives `{request}` and
  may also use `{output}`. No shell interpolation is performed.
- `corpus_command`: argv for a genuine frozen auction collector. The existing
  `scripts/collect_ben_auctions.py` now accepts `--input-corpus` to preserve the
  loop's exact cards and identities. Its substitutions are `{input}`, `{output}`,
  `{count}`, `{seed}`, and `{exclusions}`. Output is `{output}/frozen.jsonl` in
  exactly input order; only auction and resulting contract may change.
- `bots.ben`: the fixed full-search server endpoint, source revision, config,
  and a nonempty model manifest mapping absolute model paths to SHA-256 hashes.
  `operator_verified` records that the running HTTP server actually uses those
  files. The client verifies local hashes but cannot independently attest a
  remote server's internal configuration. No server is started automatically.
- `pinned_files`: external scripts/config/model files used by the bidder/trainer.
  Local package/scripts/native sources and solver are hashed automatically.
- `exclusion_files`: optional JSON files with `{"deal_ids": ["sha256", ...]}`
  covering prior data. Fresh namespaced random deals also prevent intentional
  reuse; the ledger protects everything created during the campaign.

Example collector argv (use actual absolute paths):

```json
["/path/to/ben-venv/bin/python", "scripts/collect_ben_auctions.py",
 "--ben-dir", "/path/to/ben", "--config", "/path/to/neural-only-bid.conf",
 "--input-corpus", "{input}", "--count", "{count}", "--seed", "{seed}",
 "--exclude-groups", "{exclusions}", "--out", "{output}"]
```

For an auction-belief-only v2, a runnable reference learner is supplied:

```json
["/path/to/tf-python", "scripts/loop_train_auction.py", "--request", "{request}"]
```

It warm-starts the parent's eight-array auction model, trains on new train-split
deals, retains the parent as the epoch-zero choice, selects by validation NLL,
exports NumPy inference weights, and never uses the internal test or arena.
It deliberately refuses a different parent factory. It is useful for checking
the plumbing or a belief-only branch; choose the actual final v2 learner for the
combined belief/policy loop. Auction-only training sees the same auction-label
distribution when bidding is frozen; stronger play alone does not create better
auction-only labels. Policy/play-aware learning is where changed trajectories
can provide a new signal.

```sh
python3 -m bridge_harness.improvement init \
  --config /path/to/experiment.json --root runs/v2-loop
python3 -m bridge_harness.improvement check --root runs/v2-loop
# Later, when ready to spend the compute:
python3 -m bridge_harness.improvement run --root runs/v2-loop --generations 1
# The same command resumes interrupted work.
python3 -m bridge_harness.improvement status --root runs/v2-loop
python3 -m bridge_harness.improvement report --root runs/v2-loop
```

`progress.md` and `progress.json` record every candidate, sample size, IMP results
against original/parent/BEN, BEN improvement, uncertainty, timing, and decision.
`state.json` preserves v3/v4/... aliases and the actual immutable candidate names.
Only runtime directories contain data, weights, logs, SQLite state, and raw
matches. They are excluded from Git; source, tests, recipes, and this runbook are
versioned. A long run must execute on a persistent worker, not rely on this chat
remaining alive.

## Final trainer interface

The request JSON contains `dataset`, its SHA-256, `parent_manifest`,
`parent_identity`, a deterministic training `seed`, and an `output` path.
The dataset lists immutable self-play shards and the allowed fit/selection splits.
The selected result is written atomically to `output`:

```json
{
  "bot": {
    "factory": "your_v2_module:make_player",
    "kwargs": {"belief": "$artifact:belief", "policy": "$artifact:policy"},
    "budget": {"samples": 32, "objective": "tricks", "batch": true, "near_tie": 0.125},
    "artifacts": {"belief": "/path/belief.npz", "policy": "/path/policy.npz"}
  },
  "training": {
    "dataset_sha256": "COPY_FROM_REQUEST",
    "parent_identity": "COPY_FROM_REQUEST",
    "seed": 123,
    "selection_split": "validation",
    "test_access": false
  }
}
```

Copy the actual request seed. The factory returns the existing
`choose(observation, rng)` player interface and logs behavior probabilities,
PIMC estimates and any search costs. Factory modules must be in the pinned
checkout or have their source hash verified through the registry. Do model and
hyperparameter selection on validation; submit one frozen candidate per data
stage. Record separate belief/policy validation diagnostics in `training` so a
failed generation can distinguish insufficient data from an unhelpful target.

## Validation performed

The new tests exercise full synthetic self-play → trainer handoff → paired arena
at two cumulative sizes, restart/cache reuse, score orientation, immutable copied
weights, writer exclusion, data overlap rejection, changed-corpus rejection,
failed-game blocking/retry, and both promotion endpoints. Synthetic campaigns
are visibly labelled and cannot promote a production bot. The fixture trainer
submits a fixed simple player (or copies a parent for the unchanged-weight test)
and is not a learning result. See the branch validation report
for the actual test outcome and boundaries of what was run.

Original bridge rules, scoring, PIMC, constrained sampler, replay harness, and DDS
integration are reused from this repository. Auction belief code is reused from
the existing bidding study. BEN and DDS retain their upstream attribution and
licenses; BEN's external source/weights are not redistributed. The loop was
implemented by OpenAI Codex in collaboration with Max Schireson.
