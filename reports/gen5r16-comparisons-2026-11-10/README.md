# Gen5 16/32-budget comparisons — 10 November 2026

Two prespecified 100-family paired cardplay tests, sharing the same 100 new canonical test-bucket deals and current Gen5 neural-only auctions. Each comparison swaps NS/EW partnerships between two rooms; positive IMPs favor the first bot. All four variants use the same Gen5 policy, belief and bidding weights.

| Match | Candidate | Baseline |
|---|---|---|
| 5R16 vs Gen5-32 | Representative16; policy window 0.125 tricks | Random32; policy window 0.125 tricks |
| 5RZ16 vs 5R32 | Representative16; policy window zero | Representative32; policy window 0.125 tricks |

Representative sampling applies with 10–13 tricks remaining: draw four times the DDS budget, cluster and fit belief moment weights, then solve at most the budget. Later positions use ordinary random sampling at the specified budget. This preserves the current Gen5R recipe, scaling its budget only. The Z variant restricts policy ranking to the PIMC-best tie set (numerical tolerance 1e-9).

Play uses common history-based random streams across variants and comparisons. Whole-board IMP differences, not individual decisions, are the statistical units. The two tests share deals and must not be pooled as 200 independent families. Passouts remain in the denominator. No data-dependent stopping or deal selection.

The runner validates every chosen move against its configured PIMC window, checks sampling budgets, replays all completed tables and independently recomputes IMP scores. Tables are saved before pairing and can be resumed. It freezes model, code, DDS binary and auction hashes before play. Single-thread process CPU and wall time are recorded per decision, excluding model loading; timing remains descriptive because the bots may choose different lines.

Run from a restored checkout:

```sh
python scripts/match_gen5r16.py run --run runs/gen5r16-100
python scripts/match_gen5r16.py summary --run runs/gen5r16-100
```

Status: running. Final results will be added after all 100 boards per comparison complete.
