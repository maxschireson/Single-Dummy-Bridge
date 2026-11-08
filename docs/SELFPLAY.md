# Batch PIMC self play and learning data

This is a working data collector, not a trained stronger bot. All four seats
play PIMC, with declarer controlling dummy. Each non-forced decision draws a
fresh set of worlds conditional on visible cards, counts and observed voids.
The sampler does not yet use the likelihood of earlier card choices or bidding.

## Run and reproduce

```sh
python3 scripts/build_dds.py
python3 -m pip install numpy  # export and its validation test; play itself is stdlib-only
python3 -m unittest discover -s tests -v
python3 -m bridge_harness.selfplay --count 1000 --workers 8 --samples 32 \
  --deal-seed 20261110 --seed 9173 --objective tricks --near-tie 0.125 \
  --out data/selfplay-1000-32
```

Add `--resume` with the same settings to skip already completed games. Each
game runs in its own process with a hard 300-second default deadline, including
native solver calls. Eight workers means at most eight live game processes.
The same PIMC context is used for every decision within a game; its allocation
is retained, but proofs are cleared at each decision boundary. There is no GPU
dependency. Worker count and destination may change at resume; corpus, source,
library, sampling, exploration and decision-seed settings must match.

`--episodes 4` produces four independently randomized trajectories per deal.
Those remain one independent deal, and must not be counted as four independent
strength measurements. The decision seed is separate from the deal-generation
seed and only uses public history, controller and board ID. Reproducibility is
independent of worker scheduling.

`--corpus corpora/frozen.jsonl --count 1000` uses a fixed corpus instead.
The default generator's contracts/auctions are synthetic scaffolding, explicitly
not a tournament bidding distribution. Initial data can teach play-conditioned
inference and continuation values, but cannot teach realistic auction inference.
Freeze real auctions before any claims about auction-conditioned strength.

Every complete game is replay-validated before saving an atomic compressed
shard under `episodes/`. Partial/error/timeout games go under `failures/` and
contribute no training examples; a resume retries failures. Never silently
discard failures in comparisons. A `.writer.lock` prevents concurrent writers;
after a crash, check that no writer remains before removing a stale lock.
The summary reports only completed games; after an abrupt crash without a final
summary, elapsed-wall-time accounting does not recover the lost session, so
measure uninterrupted runs for throughput. This does not lose completed shards.

## Batch integration

The original Faster-DDS batch API returns one best score per layout. PIMC needs
every legal card scored, so `native/pimc_batch.cpp` adds an all-moves C binding.
It uses the existing related-layout validator, compact relative-rank table, and
native transposition-table reuse in DDS mode 2. It expands DDS equivalent cards
back into individual legal card values. The default table implementation is
DDS's Pattern table (the original harness used Large).

Validation covers every world before any search: no duplicated cards, correct
counts, valid ranks/strain/leader, consistent partial trick, no observed revoke,
the same remaining deck, and preservation of every marked visible hand. At
opening lead only one hand is visible; thereafter the fixed hands may be
partners or adjacent seats. Python validates duplicate list entries before
packing cards into masks. The C boundary catches exceptions.

Batch lifetime is one decision with one trump/leader/current trick/remaining
deck. This matters because DDS mode 2 also suppresses the usual new-trump cache
reset. No arbitrary reuse across decisions or strains is attempted. Scalar root
certificates from the earlier study cannot certify the value of every move and
are not used by this all-moves path.

Use `--serial-dds` to disable related-world retention. Both modes use the same
compact-rank binary and Pattern table, so that comparison isolates batching.
The benchmark includes sampling, marshalling, validation and value aggregation:

```sh
python3 scripts/benchmark_pimc_batch.py --boards 10 --samples 32 --repeats 2 \
  --out results/batch-32.json
```

## Exploration and policy targets

For each decision, all moves are evaluated on the **same sampled worlds**.
Self play defaults to maximizing expected tricks for the acting partnership.
The bot chooses uniformly among moves within 0.125 expected tricks of the best
sample estimate. Exact ties are randomized too. This is an empirical PIMC gap,
not a guarantee that the true cost is below 0.125 tricks. The threshold has the
selected objective's units: tricks, score points or make probability. Ordinary
`match` defaults to zero tolerance to preserve its previous exact-tie behavior.

Each policy target contains:

- Chosen card, full behavior distribution and chosen probability.
- Every legal card's PIMC mean, Monte Carlo standard error, estimated gap to the
  best card, and paired gap standard error using the common worlds. The latter
  does not correct the best-card selection bias or account for PIMC model bias.
- Final tricks for declarer and the acting partnership, remaining partnership
  tricks from this state, and the acting partnership's duplicate score.
- Outcome minus the chosen move's PIMC prediction; a useful baseline-subtracted
  target, not a causal counterfactual action advantage.
- Forced-move and multiple-eligible-action masks, sample budget and objective.

For a learned selector, restrict candidate actions to the PIMC near-tie set.
Start with a small action-value or residual-value model on randomized choices
and observed returns, using PIMC estimates as a baseline and retaining behavior
propensities for off-policy experiments. PIMC means are legitimate bot-derived
features for the selector. Pure imitation of the randomized action merely
copies the exploration policy; PIMC-label distillation alone cannot teach it
which PIMC-equal moves work better in actual play.

Only the chosen action has a realized outcome; unchosen actions do not acquire
counterfactual return labels. Many equal moves may be strategically equivalent.
If return noise overwhelms the signal, add a targeted branching teacher: replay
the same pre-action information state, force each eligible action, and run
multiple information-legal continuations on held-out worlds. Do not train on
full-information DDS values as if those were single-dummy action outcomes.

## Belief targets and information boundary

The input is a serialization of the runner's immutable **pre-action**
`Observation`: controller, actor, visible remaining hands, legal moves, ordered
public play/current trick, leader, contract, dealer, vulnerability, public auction,
and tricks already won. The current chosen card and future play are absent.
Dummy remains concealed until after the opening lead and is controlled by
declarer. Actual hidden cards, deal seed and final outcomes never reach the bot.

Only after the game finishes does the exporter replay it and attach labels:
the true remaining owner of every card (N/E/S/W=0/1/2/3, played=-1), a mask of
hidden remaining cards, and true remaining suit counts by hand. The initial
four hands are also preserved in the privileged replay record. Those are
labels/audit material, not model inputs. True remaining owners plus public play
recover original ownership if a later training objective needs it.

For a first belief net, train masked owner cross entropy on **unseen and still
uncertain** cards; assess held-out likelihood/calibration against the existing
count-and-void constrained sampler. Deterministic ownership from hard knowledge
should not inflate the apparent improvement. Card marginals alone are not a
joint deal sampler: at inference enforce exact remaining counts, visible cards,
voids, and card uniqueness when sampling, using constrained proposals or
likelihood weighting. Evaluate sampling effectiveness and playing strength too.

Avoid conditioning the model on its own sampled worlds as if they were truth.
The true hidden hands in these records come only from the actual played deal.
Initially all opponents use the same PIMC policy. Generalization to other skill
levels, signaling styles and bidding systems requires a broader opponent mix.

## File schema and export

Each `episodes/ID.json.gz` has `schema_version`, `episode_id`, `episode`,
`record` (complete replay including all actual hands), and `examples` (52
pre-action rows for an ordinary full game). Example fields are:

| Field | Meaning | Use as model input? |
|---|---|---|
| `observation` | Only information available before the action | Yes |
| `policy_target.pimc` | Bot-computed action values | Yes, for the PIMC selector |
| `policy_target` other fields | Chosen action, propensity, returns and masks | Labels/loss construction |
| `belief_target` | Actual hidden ownership and shapes | Labels only |
| `metadata` | Episode, deal, group, ply, split, auction source | Grouping/audit only |
| Outer `record` | Complete actual deal and final replay | Audit/reconstruction only |

Cards are 0..51 in S2..SA, H2..HA, D2..DA, C2..CA order. JSON policy dictionaries
use stringified integer card keys. In bot replay details they use symbols such
as `SA`; the exporter converts them. Nothing is shuffled at the decision level
before splitting.

Splits are deterministic 80% train, 10% validation, 10% test by a hash of the
actual original hands. Declared fixed-N/S deal families hash the fixed N/S cards,
so all E/W variations stay together. Preserve `family` metadata on related
corpora; do not mix renamed/copy corpora that drop it. All repeated trajectories
of a deal inherit its split. Augment seats/suits **after** splitting, retaining
the original split group. Hold the test group untouched when choosing models.

Optional NumPy export (the playing harness otherwise has no Python dependency):

```sh
python3 -m bridge_harness.selfplay --out data/selfplay-1000-32 --export train \
  --export-path data/selfplay-1000-32/train.npz
python3 -m bridge_harness.selfplay --out data/selfplay-1000-32 --export validation \
  --export-path data/selfplay-1000-32/validation.npz
python3 -m bridge_harness.selfplay --out data/selfplay-1000-32 --export test \
  --export-path data/selfplay-1000-32/test.npz
```

NPZ input arrays contain visible/played cards, observed voids, ordered padded
history, legal-card masks, hard owner-support masks, remaining counts and public
context. Owner targets and loss masks, chosen-action targets, returns, behavior
probabilities, PIMC values, selector masks and split identifiers are separate
arrays. Auctions are preserved in JSON but intentionally omitted from this
initial tensor encoder because the synthetic auctions carry no hand evidence.
The owner-support mask encodes visibility, observed voids and zero remaining
counts; it does not implement all deductions from joint hand capacities. The
exact constrained sampler remains the appropriate baseline for those deductions.
The exporter currently materializes one split in memory: export run shards
separately for larger datasets, or stream `training.iter_examples()` into a
minibatch loader. Never combine input and target arrays indiscriminately.

## What would establish improvement?

The first dataset is an integration/learning-pipeline pilot. More positions do
not automatically mean a stronger bot, and 52 positions per deal are strongly
correlated. Report independent deals, unique families, choices and failures.

Start with a small belief model (roughly 0.1–1 million parameters is a practical
experiment range), then a small residual selector. These sizes are engineering
starting points, not an empirically optimized recommendation. Learn hard
constraints algorithmically; let the net focus on information in actual choices.
Use board-balanced minibatches so long stretches of similar late positions do
not dominate. Compare early, middle and late play separately.

Evaluate belief-only, selector-only, and both against a frozen baseline on fresh
deals and against frozen external opponents. Use paired seat swaps and matched
wall-clock budgets; a model that improves estimates while slowing search may
still lose at equal time. Report tricks per board, uncertainty clustered by deal
family, and improvement per time doubling:
`delta_tricks / log2(candidate_time / baseline_time)` when times differ; also
report raw time and equal-time results because the ratio is unstable near 1.
No playing-strength gain has been established by collecting this dataset.

All source, validation and compact reports belong in Git. Bulk game records,
training arrays, logs, native binaries and weights remain outside Git.

For the requested 10,000-game first dataset, validate all ten 1,000-game
directories together before any training:

```sh
python3 scripts/audit_selfplay.py --expected-games 10000 --out data/audit-10000.json \
  data/chunk-0 data/chunk-1 data/chunk-2 data/chunk-3 data/chunk-4 \
  data/chunk-5 data/chunk-6 data/chunk-7 data/chunk-8 data/chunk-9
```

This replays every game, checks pre-action observations and hidden labels,
rejects repeated original deals and cross-split groups, and verifies the fixed
32-sample/0.125-trick collection settings. Failed or incomplete chunks do not
qualify. No training command is included in the collection workflow.
