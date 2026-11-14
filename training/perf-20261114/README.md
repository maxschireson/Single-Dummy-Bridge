# Stu loop performance (perf session, from 14 November 2026)

Work in progress. Measurements and speedups for the Stu loop's three stages (collection and rows, training, tests),
made in the perf session's sandbox (2 cores, Intel Xeon Sapphire Rapids with AMX, 2.1 GHz) unless a box is named.
The boxes are AMD EPYC 9V74 (Zen 4, no AMX), so the sandbox's ratios are a guide, not the boxes' numbers.
Branch `perf/stu-20261114`, cut from `research/rollout-loop-20261113` at `cf390da`.

## Where a pure-Stu self-play table's CPU goes (stu3-psa~stu3-psb, one table a board, fp32, py-spy, 8 boards)

| Part | Share |
| --- | --- |
| Rollouts (`X8Player.roll`) | 63% |
| of which the net's forward pass in the main rollout batches | about 52% |
| of which the fork continuations (`x8_rollout._finish`, 2 rows a call) | 10% |
| Reading the layouts (`read_layouts`) | 34% |
| of which the hand-fit scorer (`FitScorer.log_score`) | 22% |
| of which the net reading the play (`play_log_likelihood`) | 13% |

Net calls in 4 boards: 21,603 calls, 1.04 million rows. 52% of the calls carry 1 or 2 rows (7,067 of 3 boards' calls
are fork continuations), and those calls are bound by reading the weights (0.6 ms a call at 2 rows against 0.03 ms a
row at 512). The forward pass at 512 rows reaches about 90 GFLOP/s on one core (2.48 M multiply-adds a row for round
3's net): near the core's peak, so the per-row cost leaves little; the levers are calls, shapes and rows.

## 1. bf16 batches padded to fixed sizes (done: `gen7_net.bucket`, `Bf16Forward`, `FitScorer`)

oneDNN builds and caches a kernel for each new matrix shape. The rollouts' batch sizes change call by call (rows end
at claims, forks come and go), so with `BRIDGE_NET_BF16=1` a worker kept building kernels, and the kernel cache grew
to its capacity. Padding each bf16 call with zero rows to one of about 25 sizes (at most about a quarter more rows)
and cutting the padding off the outputs:

| Synthetic, round 3's net, 3,000 calls of 1 to 700 rows | rows/s | memory added |
| --- | --- | --- |
| unpadded | about 12,000 | 1.1 GB |
| padded to the buckets | about 41,000 | 0.16 GB |

| Self-play, 6 boards (seed 777, deals 400-405), one worker | CPU-s a board | peak worker memory |
| --- | --- | --- |
| fp32 | 23.1 | |
| bf16, unpadded (as the boxes run now) | 26.0 | 2.3 GB |
| bf16, padded | 13.9 | 1.4 GB |

The padded and unpadded runs play the same 312 cards (`bench/cmp_plays.py`), and the outputs are bit-identical on
this machine's kernels (`tests/test_bf16_buckets.py`). Not yet measured on a Zen 4 box, where bf16 has no AMX and the
gain will be smaller; the memory growth the loop saw there (3-4 GB a worker, README "Speed of a table") fits this cause.
`BRIDGE_NET_BUCKETS=0` turns the padding off.

## 2. Fork continuations in the main batch (done: `x8_rollout.FORK_BATCH`, `Seats.cards_pair`)

At the step a fork is taken its two copies have played as many cards as the main rows, so from then on they ride in
the main rows' batches (one net evaluation a ply for both; no claims for them, as before). They draw from their own
stream (`Seats.fork_rng`), so the main rows' draws do not depend on them. `BRIDGE_FORK_BATCH=0` restores the old path
(copies finished after the main loop from the main stream); `=2` is the old path on the fork stream, the reference
for checking.

| Self-play, the same 6 boards, one worker, sandbox | CPU-s a board, mode 2 (old path, own stream) | mode 1 (batched) |
| --- | --- | --- |
| fp32 | 20.6, 20.1 | 18.4, 18.2 |
| bf16, padded | 12.6 | 9.4 |

Mode 1 plays the same cards as mode 2 (6 of 6 boards in three of four pairings; in one fp32 run one board differed
from card 10, and rerunning mode 1 gave mode 2's cards again: a run-to-run difference, most likely the claim
solver's time limits, not the batching). `tests/test_fork_batch.py`: the main rows' tricks, floors, ends and lines are
identical in modes 1 and 2, the same forks are taken, and with top-card seats the forks' results are identical too.
`tests/test_x8.py` passes in modes 0 and 1. **Against the code as it runs now (mode 0) the main rows draw differently
after a race's first round**, because the old continuations consumed the main stream: same distribution, not the same
cards.

Together, in the sandbox: bf16 as the boxes run it 26.0 CPU-s a board, padded and batched 9.4 (2.8x); fp32 20.3 to 18.3.

## Proposed next

- **The hand-fit scorer's first layer as table lookups.** Its input is one-hot per suit, so `x @ Wh` is a sum of
  gathered rows (about 15% of the scorer, 3% of a table). Exact up to rounding order.
- **BEN in the tests.** BEN's answer is a function of its request (hand, auction, dummy, cards played); a cache of
  requests shared by the matches on the same deals (every bot's gate runs the same 2,560 deals) serves BEN's opening
  leads and the plays before a bot's first different card without asking BEN. To measure first: the share of BEN's
  requests in two gate runs on the same deals that are equal.

## Files

| File | What |
| --- | --- |
| `bench/fwd_bench.py` | rows/s of the fp32 forward pass by batch size, and its time split |
| `bench/bf16_bench.py`, `bench/bucket_bench.py` | bf16 rows/s by batch size; memory and throughput over varying sizes, padded or not |
| `bench/instrument.py` | runs `scripts/x8_match.py` with counters on the scorer's and nets' calls (rows, time, callers) |
| `bench/fold.py` | summarizes a py-spy raw profile by function |
| `bench/ab_run.sh`, `bench/cmp_plays.py` | a self-play run with its peak worker memory; two runs' cards compared board by board |
| `tests/test_bf16_buckets.py`, `tests/test_fork_batch.py` | the two changes' equivalence checks |
