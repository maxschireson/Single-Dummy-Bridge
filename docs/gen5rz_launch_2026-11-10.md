# Gen5RZ allocation and policy ablation

Gen5RZ (32) clones the frozen Gen5R (32) actor, with `near_tie=0` and an
explicit `pimc-ties-only` policy role in its identity. The policy ranks only
PIMC winners; unique winners bypass it. The existing numerical tolerance handles
floating-point ties. Networks, bidder, belief sampler, representative layout
selection, calibration and sample budgets are unchanged. Existing R actors
retain their original identities and 0.125 near-tie margin.

| New matchup | Share | Entries per shuffled block |
| --- | ---: | ---: |
| 5RZ32 vs 5R32 | 30% | 111 |
| 5R32 vs original Gen5 (32) | 20% | 74 |
| 5R32 vs 4b | 21.6216% | 80 |
| 5R32 vs 3 | 10.8108% | 40 |
| 5R32 vs 2 | 8.1081% | 30 |
| 5R32 vs 1 | 2.7027% | 10 |
| 5RZ192 vs BEN (16) | 2.7027% | 10 |
| 5R32 vs 5R192 | 4.0541% | 15 |

A full block has 370 deals. The first two rows occupy half; all other rows
retain their previous relative 16:8:6:2:2:3 weighting. A partial final block and
out-of-order completions can temporarily differ from the scheduled percentages.
Both common bidding and native partnership bidding, swapped rooms and existing
training forks remain in use. The new Z comparison is 32 vs 32; Z192 takes over BEN, which remains
neural-only with 16 samples. Three ordinary workers and one BEN worker continue.

The handoff drains `/workspace/work/gen5r`, preserves its manifest and completed
records, and freezes only its remaining deals in `/workspace/work/gen5rz`.
The new checkout is `/workspace/Single-Dummy-Bridge-5rz`; its publication branch
is `arena-gen5rz-feed`. No completed record is relabeled or replayed as new
evidence. Earlier compatible Gen5R observations remain in the current report;
Gen5 and earlier generations remain under Older. Raw episodes, checksums and
full PIMC estimates remain available for training.

`configs/round5rz.json` fixes the allocation; `ops/prepare_gen5rz.py` validates
and freezes the zero-margin actor and unplayed corpus. The generic collector
and its runtime are unchanged. The policy ablation therefore uses the same
core source checksum as Gen5R, with a distinct actor and cohort identity.

Validation includes exact allocation ratios, unchanged actor configuration,
policy rejection of lower PIMC moves, policy selection among exact ties,
bypassing policy for unique winners, every matchup's sample budgets and bidding,
and preservation of completed source records during preparation. Two native
swapped games supplied 104 legal actions, 26 actual Z policy tie-breaks and zero
Z PIMC gap, including both representative and ordinary sampling positions.
See `reports/gen5rz-native-preflight-20261110.json`.

The user subsequently moved BEN to Gen5RZ (192), preserving its 10/370 share.
`configs/round5rz-ben.json` and `ops/prepare_gen5rz_ben.py` freeze that handoff.
The early Z32 cohort and all its observations stay intact and are retained in
the current comparison. Z192 clones R192 with only the zero policy margin;
existing R192-vs-BEN games remain a separately labeled baseline.

A system-Python watchdog restart failure in the retired source was preserved
under resolved-failures. The new launcher pins the training virtual environment
and propagates that choice to its children, including cache-rotation restarts.
