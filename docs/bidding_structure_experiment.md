# Bidding hand structure and attention screen — 10 November 2026

Max authorized a separate experiment adding exact card information and structure
to the post-trained bidder. This does not replace the Gen6 continuation or change
any arena bot.

## Frozen comparison

The selected Gen5 BEN-compatible bidder (three 256-unit LSTMs) is frozen.
Its probability distribution and final 256-dimensional state feed each small
adapter. An initially zero correction to log probabilities makes every arm start
at the same bidder. Only the adapter and its training-only value head learn.

| Arm | Hand representation | Public auction representation | Parameters |
| --- | --- | --- | ---: |
| dense_compressed | A/K/Q/J/T and low-card count per suit | Learned call/relative-player embeddings, ordered fixed slots | 54,525 |
| dense_exact | Every rank in each suit | Same dense auction representation | 55,421 |
| attention_exact | Exact ranks, shared suit encoder, suit identity | One attention layer over calls with position and relative-player embeddings; four suit queries attend to calls | 55,625 |

All arms also receive suit length, HCP, controls, vulnerability, opening position,
and the same frozen parent outputs. Both exact arms receive the same information.
The compressed arm cannot distinguish low ranks. Full 320-call capacity avoids
truncating legal auctions; attention evaluates only the actual prefix and masks
padding. Hidden partner/opponent hands never enter any actor or value-head input.

Each arm receives 2,048 paired deals for each of two initialization/sampling seeds
(101 and 202), with identical deal sampling across arms at each seed. Half the
training pairs use clean actual-play rewards and half use existing DDS labels.
Sampling stays on policy; a historical greedy action is never treated as a PPO
sample. PPO uses two epochs, 64-decision minibatches, 1e-4 adapter learning rate,
0.005 exploration, 0.02 KL retention to the frozen Gen5 parent, clipping 0.2,
and the existing IMP/10 critic scale. The larger adapter learning rate and the
Gen5 anchor are explicit experimental choices, separate from unchanged Gen6.
All architectures use the same optimizer settings and training budget.

## Data and evaluation

The pinned dataset SHA-256 is
`5639592328092130a5d94e5b8954759b17fff0589ce488453ba1c763dbd30cc5`.
It has 40,000 DDS training deals and 2,659 clean played training deals; development
uses 1,000 DDS deals and 353 clean played deals. No family crosses partitions.
The 192 historical test deals and 177 fresh confirmation deals are excluded from
training and development. No final test is automatically opened.

Existing clean-play provenance exclusions reject v4/v4p as declarer or defender.
Reward reuse requires the exact oriented deal, full auction, dealer and
vulnerability. Missing auctions are played with the same frozen clean Gen3/32
configuration as the earlier bidding refresh. Completed compatible cache files
are copied; the new experiment owns its SQLite cache and output files.

Development reports each adapter against the unchanged parent, plus paired
exact-minus-compressed and attention-minus-exact differences. For the aggregate
paired comparison, seeds are averaged within family before computing the SE;
seed results are also reported individually. These are development screens,
not untouched final tests. Historical parent exposure and small played validation
volume limit what the screen can establish. A promising arm needs fresh,
larger confirmation with actual play before a strength claim or promotion.

## Validation and measured timing

Focused tests verify that changing a low rank changes only the exact input,
auction roles and order are correct, all three initial policies match the parent
distribution, on-policy likelihood ratios start at one, gradients update the
correction, and checkpoints restore the predictions and optimizer completely.

A 32-pair / 339-decision timing probe measured:

| Arm | Collection including model load | Two update epochs including tracing |
| --- | ---: | ---: |
| Dense exact | 3.97 s | 0.93 s |
| Attention exact | 4.66 s | 2.56 s |

Both probes reached five rooms requiring an exact-auction play lookup. Probe
updates used synthetic rewards solely for timing; they are never training
checkpoints. Earlier clean Gen3/32 replays averaged 3.87 seconds each. Initial
planning estimate: 1–2 hours for the first seed's three-arm comparison and
2–4 hours for both seeds plus development. Novel-auction frequency and cache reuse
are the main uncertainty; estimates should be updated from real batches.

## Running and resuming

From the repository root, with the existing TensorFlow environment:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3 TF_ENABLE_ONEDNN_OPTS=0 \
  /workspace/scratch/bbe90ba77a68/venv/bin/python scripts/run_bidding_structure.py \
  --config configs/bidding_structure.json --stage run
```

The config records absolute source paths for this host; adapt those paths after
restoring the pinned inputs on another host. The supervisor owns a nonblocking
file lock and resumes completed stages/checkpoints. It separates TensorFlow
collection/updates from DDS cardplay processes. Runtime files are under
`runs/bidding-structure-20261110`: `manifest.json`, `status.json`, `pipeline.log`,
per-arm `state.json`, immutable batch records, weights, development outcomes,
then `results.json` and `complete.json`. Frozen input/source hashes are checked
at each stage. Inspect log errors before restarting; do not change a frozen
recipe in place. No promotion or final-test selection is automatic.
