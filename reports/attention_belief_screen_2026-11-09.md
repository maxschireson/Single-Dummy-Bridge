# Small attention belief screen

The hypothesis is that explicit attention over card, auction and play tokens,
combined with greater ownership-loss weight at consequential decisions, improves
useful beliefs. This is a standalone owner predictor, not belief+; there is no
trick or outcome head. No production bot is changed by this experiment.

## Fixed single-candidate recipe

- Two pre-norm transformer layers, width 128, four heads, feed-forward width 512,
  dropout 0.1: **431,236 trainable parameters**. The frozen v4 dense model has
  308,726. The original 1.8M proposal was reduced before any candidate fitting,
  following Max's training-bandwidth constraint. No architectural size sweep.
- Own visible cards, dummy when exposed, contract, vulnerability, legal moves,
  voids and hand capacities; ordered auction and public-play tokens. Relative
  seats; suits are not permuted. A shared card head predicts remaining owners.
- Sparse cross entropy only on uncertain cards. Played, visible and forced
  owners are excluded; impossible seats are hard-masked. Hidden cards supply
  targets only, never inputs or importance signals.
- Up to 16 positions per canonical deal family from original root trajectories,
  spread across four play stages. All auctions/tables/rotations of a deal remain
  together. Audit-fork copies do not inflate the sample.
- Frozen mixture of 24 v4-weighted and eight uniform **legal** worlds per
  decision. DDS scores all legal actions in each world. The importance signal
  is the expected advantage of knowing the world before choosing an action,
  versus choosing the best action averaged over worlds. Utilities are signed
  IMPs relative to the current contract making exactly, a common reference
  across actions. Weight is `1 + 3 * min(EVPI / 2, 1)`; forced actions get 1.
  This is a DDS-based importance heuristic, not achievable single-dummy regret.
- Normalize the weights to equal total mass per family. Ordinary positions keep
  positive weight. Report weighted and unweighted validation measures.
- Three epochs from scratch, one fixed seed; AdamW 0.0003, weight decay 0.01,
  100-step warmup and gradient norm clipping at 1. Checkpoint model, optimizer
  and RNG every 100 batches and every epoch; retain the best validation-weighted
  NLL checkpoint. A filesystem lock prevents concurrent writers.

## Data and evaluation limits

Source episodes come from the component and supplemental Gen4 arena streams.
The initial snapshot contains 3,990 training families, 512 validation families
and 496 reserved test families. The training-position ceiling is 63,840;
positions with no uncertain owners and passed-out deals reduce the exact count.
The frozen manifest hashes every source; preparation writes individually hashed,
resumable family shards. Existing modulo-5 train/holdout assignments are
preserved, with held-out families split by modulo 10: 0 final test, 5 validation.
Test families are excluded from position preparation, fitting and metrics.
One family used for an initial serialization preflight was subsequently found
to be in the test bucket and is explicitly retired from this experiment's pool;
no training or prediction metric used it.

V4 continued an already trained network on **126,608 training families,
1,630,369 positions and 47,247,357 uncertain-card targets per pass**. Its corpus
includes broad auction supervision as well as play. This deliberately smaller
screen uses only recent public-play positions from several thousand families
and starts from scratch. Therefore a loss to v4 would not isolate architecture
quality. Learning curves and an unseen-family generalization gap matter. This
screen does not establish an improvement in IMP strength.

Report validation ownership NLL, Brier score and accuracy overall and for early
play, later play, declarer/defender and suit/notrump. Compare v4 on exactly the
same rows and bootstrap/cluster by deal, never by independent cards. The code
reports a paired family-mean NLL difference and its cluster standard error.
Final test remains reserved for a subsequent frozen selection. Before promotion,
run paired play with policy, sampler, objective and 32-world budget held fixed.

## Running and resuming

Requires Python 3.12, NumPy and CPU PyTorch 2.5.1; a built compatible DDS library;
the frozen v4 checkpoint; and the source episode directories. No GPU required.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python scripts/screen_attention_belief.py \
  --output runs/attention-v5-screen-20261109 \
  --parent models/belief-v4.npz \
  --sources /path/to/components-run /path/to/supplement-run \
  --workers 2 --threads 1 --batch-size 32
```

Reissuing the same command verifies and resumes existing shards and optimizer
state. `--stage prepare` and `--stage train` permit separate execution. Do not
change the frozen data, model dimensions, batch size or split on resume. Status
and per-epoch metrics are atomically written under the run directory.

The four targeted tests check independence from hidden hands, owner-support
legality through an entire deal, consequence weighting for action reversals,
masked gradients and exact checkpoint round trips.
