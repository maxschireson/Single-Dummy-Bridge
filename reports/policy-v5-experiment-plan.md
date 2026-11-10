# Clean v5 policy capacity comparison

Start all candidates from the later v3 policy
`8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5`.
Fit observed remaining partnership tricks, not IMP-difference labels.

| Candidate | Parameters | Initialization |
| --- | ---: | --- |
| Original dense | 39,512 | Exact v3 weights |
| Double-width dense | 80,136 | Function-preserving neuron duplication |
| Small attention extension | 99,161 | V3 plus zero-initialized residual readout |

The attention extension uses 64-wide tokens, two heads and one cross-attention
block. Candidate moves and a value query attend to 52 visible-card tokens,
64 ordered auction tokens and one public-context token. Card tokens include
known ownership, played ownership, current-trick ownership and play order.
Padding auction calls are masked. No hidden card ownership is supplied.
All variants retain the original observable inputs and PIMC candidate window.

The data preparation allowlists v2/v3 policy hashes and PIMC-only players;
v4 and v4p are excluded regardless of seat. Recovered pre-v4 full games and
branches are combined with clean local arenas and the full remote play export.
Parent-era rotation groups are excluded from this incremental fit. Earlier
experience is retained through v3 initialization, not counted as new data.
All rooms and branches of a canonical family share one split and total weight.
Every used continuation is legally replayed and its score checked. Replayed
branch prefixes contribute no duplicate labels.

Each fit has eight epochs at learning rate 0.0002, AdamW weight decay 0.0001,
clip norm 1 and batch size 128. Validation-family MSE selects the epoch, with
epoch zero eligible. The architecture comparison uses validation MSE; branch
choice results on held-out deals are descriptive and cannot establish full-game
strength. Previously inspected test families are distinguished from fresh ones.
Nothing is automatically promoted into the arena.

Initialization and portable NumPy inference checks pass for all variants,
including a nonzero attention readout and a save/restore round trip.
On this CPU, a synthetic-batch timing check (128 rows, 25 steps after warmup,
one thread, no GPU) measured 2.28 ms original dense, 3.22 ms double-width dense,
and 55.29 ms attention per training step. These exclude loading and validation
and are not a full-run wall-clock estimate.

A separate NumPy single-position timing check with 13 candidate moves and all
64 auction slots populated measured 0.034 ms original dense, 0.039 ms wide,
and 0.248 ms attention (1,000 calls after warmup, one thread). This benchmarks
the scorer only, excluding observation encoding and PIMC search.

A wider PIMC window and trick-distribution objective are separate experiments;
neither is silently combined with the clean-data/capacity comparison.
