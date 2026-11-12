# Frozen 21,904-pair bidder: completed 5,000-pair confirmation

On 8 November 2026 the fixed held-out confirmation completed all 5,000
independent deal pairs (10,000 auctions). Candidate and BEN bid greedily;
DDS scored final contracts. No card play was simulated.

| Measurement | Result |
| --- | ---: |
| Candidate training pairs | 21,904 |
| Confirmation pairs | 5,000 |
| Total IMP difference | +372 |
| IMPs per paired board | +0.0744 |
| Descriptive 95% paired t interval | [+0.02459, +0.12421] |
| Wins / losses / ties | 149 / 128 / 4,723 |
| Pairs with different auction transcripts | 410 |

There are 5,000 unique canonical deal families, with zero overlap with either
development screen. The test split is disjoint from training by construction.
Parent, original BEN and older league are all B0: these are one comparison,
not three independent replications.

The result supports a modest gain at the ordinary 95% confidence level, but
does **not** clear the campaign's stricter promotion threshold. Applying even
the original three-stage threshold (alpha 0.05/(1*2*3*3)) gives
[-0.00165,+0.15045]. Accounting for five candidate stages would widen that
to [-0.00553,+0.15433]. These threshold comparisons are descriptive sensitivity
checks, not a retroactive migration of the production promotion schedule.
Neither permits promotion. No model was promoted.

The user reduced the fixed confirmation target from 10,000 to 5,000 before
any confirmation IMP results were inspected. The first 1,024 completed pairs
were retained; seed, frozen model and split were unchanged. Later requested
interim reports did not alter the fixed stopping point. In accordance with
the user's direction, this evaluation ends at 5,000; continue training rather
than extending the sample.

Production training had reached 33,040 pairs / 66,080 auctions / 259 updates
when this report was prepared, with zero promotions. Next configured
development screen: 50,000 training pairs. The production config retains
5,000-pair confirmations.

Operational notes: this supervision resumed stopped workers at 30,992
training pairs and 3,712 confirmation pairs. The remaining 1,288 confirmation
pairs completed in 486.9 seconds of this resumed evaluation session. The
summary elapsed_seconds field describes only that last session, not total
evaluation compute time or wall-clock duration. One supervised production
chunk paused normally after its five-minute budget at 32,272 pairs; it was
resumed and committed further updates. Earlier unexplained stops remain
unresolved. Runtime source/config hashes and data splits were preserved.

Reproduction: scripts/review_bidding_snapshot.py --phase confirm, snapshot
Bridge_DDS_Bidding_20k_Review_Checkpoint_2026-11-08.zip, seed 2326232714.
Snapshot SHA-256: fca1d3faf27c4befe9b0a72c8e5b095f7ac8da1866a08cd8baf9d190a8a9b2c5.
Source revision for the 5k confirmation: d4835177f6506bce6dc6978018565f07877f4943.
Results: runs/dds-bidding-21904-confirm/summary.json and 40 numeric JSON shards.
