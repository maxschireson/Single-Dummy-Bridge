# DDS-only bidding self-improvement

Start from BEN's external 1.52M-parameter GIB-BBO bidding policy, train both
partners together, and reward duplicate IMP gains using double-dummy terminal
scores. No card play, bidding search, EPBot calls, or play/belief networks are
needed during collection or evaluation. This is a separate campaign from the
card-play learning loop.

## Learning and evaluation

1. Generate independent complete deals with random dealer/vulnerability.
2. Cache all 20 DDS strain/declarer trick counts per deal in SQLite. Each worker
   has its own solver context; only the parent writes the cache. The cache pins
   the DDS library hash. Contract levels/doubles/vulnerability need no new solve.
3. Run two auctions with the same cards and metadata: learner NS versus frozen
   EW, then frozen NS versus learner EW. Reward every learner decision in both
   rooms with `IMPs(NS_score_room_A - NS_score_room_B)`.
4. Collect from a frozen learner snapshot. The learner samples its masked
   probabilities mixed with 0.5% uniform legal exploration; opponents are greedy.
   Train using clipped PPO, an own-information value head, a small B0 KL penalty,
   and entropy regularization. Returns are IMPs/10, gamma=1, with Monte Carlo
   returns; there is no bootstrapping across auctions. Adam and global gradient
   clipping are used. Rollout and PPO exploration distributions are identical.
5. Disable dropout and freeze BatchNorm statistics during BOTH collection and
   gradient passes. This keeps PPO likelihood ratios meaningful. All LSTM and
   bid-head weights remain trainable. BEN's TimeDistributed(Dense) is unwrapped
   into its equivalent Dense operation to avoid Keras 3.15 dynamic-length bugs.
6. Opponents are 50% latest champion, 25% a sampled older champion, 25% original
   BEN. At launch all three are B0. Both learner seats always use the same version.
7. At 10k, 40k and 250k cumulative training deals per attempt, screen the candidate
   on 1k fresh development deals. If all three mean results are positive, run a
   fixed 5k-pair confirmation against parent, original BEN and older league.
   All evaluation bidders use greedy legal calls, without exploration.
8. Promote only if all three adjusted confidence-interval lower bounds exceed
   zero. Alpha is 0.05 divided by `attempt*(attempt+1)*stages*3`, accounting for
   attempts, stages and endpoints. Intervals are approximate Student-t intervals,
   not exact confidence sequences. Intermediate progress is descriptive only.
   No zero-variance sample can establish promotion. Successful candidates become
   frozen B1, B2, etc.; failed final-stage candidates reset to the parent. The
   checked-in configuration caps the campaign at 20 attempts.

**Information boundary:** `BidObservation` contains only own cards, acting seat,
dealer, vulnerability and past public calls. DDS tables, other hands, rewards,
seeds and future calls never enter the actor or value network. There is no
clairvoyant best-contract target. DDS scores only completed auctions.

**Data separation:** a hash of the underlying deal canonicalized over compass
rotations assigns train/dev/test (80/10/10). Dealer and vulnerability never affect
the assignment. Each attempt/stage has fresh deterministic evaluation seeds.
Confirmation data is never used for gradient updates or checkpoint selection
within a stage. Neither rotated deals nor vulnerability variants cross splits.
Current collection uses fresh unique training deals; the cache also supports
reuse after interruption or repeated auction experiments.

## Running

Requires Python 3.11+, NumPy, SciPy and TensorFlow/Keras compatible with the
external checkpoint. The launch was tested with Python 3.12 and TensorFlow 2.21.
Build the Apache-licensed bundled DDS with `python scripts/build_dds.py`.
Obtain BEN's external checkpoint from https://github.com/lorserker/ben and retain
its applicable license/provenance. The initial configuration expects the
193-feature GIB-BBO model, system identifiers 1/1 and unadjusted HCP.

```bash
python scripts/audit_bidding_loop.py \
  --ben-dir /path/to/ben \
  --model /path/to/ben/models/TF2models/GIB-BBO-8742_2026-10-23-E30.keras \
  --dds-library /path/to/libbridge_dds.so

python scripts/run_bidding_loop.py \
  --run runs/dds-bidding-v1 \
  --initial-model /path/to/ben/models/TF2models/GIB-BBO-8742_2026-10-23-E30.keras \
  --dds-library /path/to/libbridge_dds.so \
  --config configs/bidding_dds.json \
  --run-seconds 21600
```

Repeat the exact command to resume. `--run-seconds` is a cooperative time budget,
checked between batches; a DDS batch/update already started is completed.
`--max-updates 1` is useful for a smoke test. A nonblocking file lock prevents two
workers from updating the same campaign. Use a different run directory for tests.

`manifest.json` pins model/solver hashes, source hashes, TensorFlow version and
all hyperparameters. Resume rejects mismatches. `state.json` advances atomically
only after model AND Adam-state checkpoints have been saved. The two most recent
optimizer checkpoints are kept; promoted `.keras` models remain separately.
The run is recoverable after a lost worker: already committed updates and DDS
tables are not recomputed. An interrupted uncommitted auction/update batch is
regenerated from the previous checkpoint and deterministic batch seed.

`status.json` reports phase, completed training pairs, DDS cache sizes, timing and
training metrics. `batches/` stores auction pairs and metrics; `evaluations/`
stores resumable evaluation shards and summaries. Positive training reward alone
does not prove improved bidding; only held-out greedy evaluation can do that.

Data, logs, checkpoints and model weights stay out of source commits. Preserve a
checkpoint bundle separately for recovery when moving environments. It must
include manifest/state, the referenced optimizer checkpoint, promoted models,
and a consistent SQLite backup; paths may require explicit migration.

`python scripts/snapshot_bidding_loop.py --run runs/dds-bidding-v1 --out checkpoint.zip`
creates a hot checkpoint using the committed state and SQLite's backup API,
including the exact baseline and solver dependencies. It does not stop training.
Source code is recovered from the recorded repository revision. Pending
evaluations are safely recomputed after restoration.

## Verification

```bash
BRIDGE_DDS_LIBRARY=/path/to/libbridge_dds.so \
  python -m unittest discover -s tests -p test_bidding_loop.py -v
```

Tests cover legality, doubled/redoubled/vulnerable scores, first-strain declarer
selection, score orientation, private-information encoding, split invariance,
all-tie/repeated-deal promotion rejection, DDS tables versus independent opening
solves, an actual policy-gradient update, and exact Adam-state restoration.
`audit_bidding_loop.py` separately compares features, legal calls and model
probabilities with the actual external BEN implementation on complete auctions.

The first audit checked 656 decisions on 64 auctions: zero feature or prediction
differences, identical legal masks, and zero IMPs for eight identical-bidder
duplicate pairs. Eight full DDS tables averaged about 0.24 seconds per deal on
one solver context; this small timing sample is not an end-to-end throughput claim.

DDS rewards omit real-play effects, including the information revealed by bids.
This is intentional for the initial experiment. Learned bidding changes should
later be reflected in the auction belief model before integration with card play.

## Confirmation budget update — 8 November 2026

At Max's request, the production configuration now uses 5,000 confirmation
pairs instead of 10,000. The in-progress additional review of the 21,904-pair
candidate uses the same fixed 5,000-pair limit. Its first 1,024 completed pairs
were retained, with the same test seed, split and frozen model. No interim
confirmation IMP results were inspected to choose this limit. Inconclusive
results lead to more training, not an expanded confirmation sample.

Both workers were paused for the documented migration. The production manifest
was changed only at config.confirmation_pairs. Hashes verified that training
state, model/Adam checkpoint, both DDS caches and completed evaluation shards
were unchanged. Runtime source hashes and promotion thresholds remain unchanged.
The before/after audit is in the run's migrations/confirmation-5000-2026-11-08
directory. The CLI default without the campaign config remains historical;
resume this campaign with configs/bidding_dds.json as documented above.

## Earlier checkpoint — 9 November 2026

Max requested cutting the next training stage at 40,000 pairs, replacing
50,000, followed directly by a fresh 5,000-pair validation. The campaign
configuration and manifest now record stages [10000,40000,250000]. At migration
there were 37,392 committed pairs. State, model/Adam checkpoint and DDS cache
were hash-verified unchanged; seeds, splits and runtime source are unchanged.
Audit files are under migrations/checkpoint-40000-2026-11-09 in the run.

For this requested checkpoint, run only the remaining updates to exactly40k
(using --max-updates), preserve the resulting recovery archive, then run
review_bidding_snapshot.py --phase confirm on that frozen archive into
runs/dds-bidding-40000-confirm. This directly evaluates5k fresh test pairs
without the1k development screen. Keep production parked at40k while this
validation runs. Do not reuse the21,904 candidate or its evaluation rows.
Report the final result for review before promoting or restarting training;
the user requested discussing the promotion threshold, not silently changing it.
