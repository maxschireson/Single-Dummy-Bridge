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

Additional implementation control: two identical 5R16 bots, with player labels swapped and a shared random stream, produced identical 52-card play and identical scores on the first fixed board. This control is not an additional evaluation family.

## Final results

All 100 prescribed families completed in both comparisons; no passouts, omitted boards or errors. All 400 table records replay-validated. The sign favors the first bot.

| Comparison | IMPs | IMPs / board | Standard error | 95% CI, IMPs / board | W–L–T | Candidate CPU / baseline |
|---|---:|---:|---:|---|---|---:|
| 5R16 vs Gen5-32 | −36 | −0.36 | 0.336 | [−1.026, +0.306] | 19–19–62 | 51.0% |
| 5RZ16 vs 5R32 | +59 | +0.59 | 0.391 | [−0.185, +1.365] | 22–11–67 | 53.1% |

The 5RZ16 result is encouraging at approximately half the CPU cost, but it is only 1.51 standard errors above zero; this batch does not establish an advantage. The 5R16 result is 1.07 standard errors below zero and also inconclusive. These are whole-board match outcomes, not per-decision or fork rewards. The second comparison changes both policy window and DDS budget, so it cannot separately identify their causal contributions. The confidence intervals use Student t across the 100 independent deal families, separately for each comparison; they are unadjusted for the two comparisons.

CPU seconds per paired board: 5R16 2.027 vs Gen5-32 3.975; 5RZ16 2.069 vs 5R32 3.896. These include sampling, weighting, DDS and policy inference. Wall times were close to CPU times. The selected PIMC gap for 5RZ16 was zero across all 4,132 nonforced decisions (3,102 reached the policy tie breaker). All 5R variants used the prescribed 64/128-deal pools and 16/32 maximum solve budgets at large positions.

See `result.json` for detailed timings and validation counters, and `board-results.json` for each paired board's score. Raw table and episode records are retained in the companion results archive. Evaluation-only status should be preserved when using these families for subsequent tests.

