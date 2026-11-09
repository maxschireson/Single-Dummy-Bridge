# Dense v5 belief: consequential-card weighting

This candidate retains v4's 308,726-parameter dense ownership network and
warm-starts its selected weights and Adam state. Attention is paused at Max's
request. This is a standalone belief model, with no value/policy head.

## Data and exclusions

The fixed clean export at `transfer/non-v4-policy-play-20261109` contains 1,944
complete games from 972 canonical deal families (767 train, 205 held out).
Both partnerships avoid policy SHA256
`e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed`.
The entire trajectory is excluded when either partnership uses 4/4p. 4b is
retained because it uses the v3 policy. Unused bot definitions in a source
manifest do not count as active players.

Merged with 818 eligible local episode records from the prior fixed snapshot,
there are 1,790 distinct families: 1,411 train, 193 validation, 186 reserved.
There are no additional family exclusions at the parent/replay boundary.
Canonical rotations and duplicate public positions stay together. The inherited
train/held-out boundary is preserved; hash modulo 10 subdivides the existing
held-out population into validation (5) and reserved (0). Reserved families
are not prepared or evaluated in this experiment. This does not claim those
families were never involved in earlier model selection.

Historical replay contributes 975,958 training positions and 123,170 validation
positions, covering public play, bidding and BEN auctions. This is the recovered
8,315-family-era replay archive, not all 1,630,369 positions used to fit v4.
The starting v4 weights retain learning from its larger fit. Historical replay
predates the bad v4 policy. The incoming clean play augments this replay.

## Consequential-card signal

Select at most 16 distinct public positions per family, stratified across four
play-depth bands. Draw 24 legal worlds from the frozen v4 belief and 8 uniformly.
Solve all legal actions in those hypothetical worlds using DDS. Convert trick
results to acting-partnership IMP utility relative to making the current
contract exactly. Actual hidden ownership and actual outcomes do not enter the
importance calculation; actual owners are only the supervised target.

For each uncertain card, estimate the decision value of knowing its owner.
Choose conditional actions on one half of the sampled worlds and evaluate on
the other half, then reverse the halves. Require at least four worlds per owner
group in both halves and shrink conditional means with four pseudo-worlds.
The card's cross-fitted gain is floored at zero; its CE weight is
`1 + 3 * min(gain_in_IMP, 1)`. Ordinary cards keep weight 1. This is a noisy DDS
information-value heuristic, not a measured single-dummy IMP improvement.
Correlations with other hidden cards contribute to information value.

Identical public positions with cached zero perfect-information value can reuse
that zero certificate under the same deterministic world sample. No ownership
labels or behavior correlations are imported from excluded policy trajectories.

## Fit and selection

- Same dense architecture and dropout as v4, three epochs, batch size 2,048.
- AdamW warm-start, learning rate 0.0001, weight decay 0.0001, clip norm 1.
- Training mass: 50% public play, 25% bidding, 25% BEN; recent families 2x.
- Normalize the total weighted uncertain-card mass within each source/family.
- Pack recent positions into normal shards so tiny family batches do not
  accidentally amplify their gradient contribution.
- Choose the lowest validation score, with the unchanged epoch-zero v4 eligible:
  25% historical play NLL, 25% recent card-weighted play NLL, 25% complete bidding
  auction NLL, 25% complete BEN auction NLL. Families receive equal metric mass.
- Report ordinary/weighted NLL, accuracy, Brier, NLL on upweighted cards, and
  paired family-cluster standard error for recent weighted NLL versus v4.

The smoke run completed checkpoint restoration, three training epochs,
validation, selected-checkpoint restoration and NumPy export equivalence. Its
small sample is only a plumbing test. Production results belong in a separate
result report after the full fit finishes. Nothing is promoted to the arena.

## Resume

`scripts/run_impactful_belief.py --config runs/dense-impact-v5-clean-20261109/launch.json`
resumes labeling and then trains automatically. A pipeline lock prevents a
second writer. Every completed family is checkpointed; fitting resumes at epoch
boundaries. The paused attention run must not be restarted.

Use Python with NumPy and the TensorFlow version compatible with the v4 optimizer
checkpoint; DDS uses the existing repository native library. Full recovery also
requires the historical `Bridge_Large_Belief_8315_2026-11-09.zip` archive and the
v4 resume archive on `research/v4-belief-and-arena`.
