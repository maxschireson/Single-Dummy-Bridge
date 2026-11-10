# Effort versus volume: initial pilot

Max authorized this experiment on 2026-11-10 to guide future collection. The first screen adds 80 Gen5 boards at 192 samples, 80 at 32, or 480 at 32 to the same frozen background dataset, with a no-addition continuation control. The main belief architecture/loss experiment and its reserved confirmation pool remain unchanged.

The high-effort source is the 102 historical-opponent records retired from arena score reporting, explicitly retained for training. Canonical holdout exclusions leave 80 training boards: 39 versus Gen4b, 18 versus Gen3, 16 versus Gen2, and 7 versus Gen1. Low-effort arms use exactly the same opponent counts and six times those counts, respectively. The smaller low-effort arm is a nested subset of the larger one. Selection is a frozen hash of deal family, without outcome selection. Three of the 480 low-effort deals are passed out, giving 477 nonempty training families. Every selected record's checksum receipt and manifest identity is checked. All inherited belief and policy families are excluded from the added data. v4/v4p policy trajectories remain excluded on both sides.

Use only shared-Gen5-auction root trajectories, including swapped partnerships. Both Gen5 actors have identical belief, policy and bidder hashes. The other partnership uses the same historical bot in the two effort cohorts. This is not a randomized paired collection experiment: the cohorts were collected at different times, and high-effort versus BEN or Gen5-32 games are deliberately excluded from this first comparison. Common roots avoid confounding collection effort with unequal fork counts.

Belief uses the existing six-epoch dense continuation recipe, the same starting v5 model, and seed, with two threads for all four arms. The first fixed-epoch comparison is emitted after one epoch, before policy work. It evaluates exact two-hidden-seat conditional NLL on 769 existing development families / 26,653 eligible positions; the full composite validation pool is also retained. Full six-epoch trajectories follow.

Policy continues the promoted attention model on observed remaining-partnership-trick targets, with the frozen original background data and the corresponding pilot additions. Use two epochs, AdamW at 0.00001, batch 128, equal family weighting, and the same seed for all arms. Evaluate fixed epochs on 593 nonempty development families (594 assigned) / 53,402 outcome positions. Test outcomes, including the 578 reserved families, are never prepared or scored here. This older development distribution may understate improvements in predicting stronger Gen5 continuations; future confirmation must include fresh Gen5 positions and actual play with common inference effort.

All paired SEs cluster by canonical deal and condition on these fitted models. One seed and one set of training subsets do not establish seed or dataset dispersion. Replicate promising contrasts with both independent seed fits and new board subsets as the stream grows. No automatic promotion or gathering-policy change follows this pilot.

Before inspecting fitted-policy comparisons, add a secondary descriptive check on fresh Gen5 hash-five development families from the same historical-opponent streams, retaining the high- and low-effort continuation cohorts separately. Original model/data families are excluded; hash-zero test families remain untouched. This pool is evaluation-only and does not select pilot models or epochs. It checks whether stronger continuation targets behave differently from older development outcomes. It is supplementary, small, and does not replace independent play confirmation.

Measured collection costs for selected records:

| Added boards | Common-root CPU seconds | Entire-record CPU seconds including forks/native rooms |
|---|---:|---:|
| 80 at 192 | 2188.33 | 2779.10 |
| 80 at 32 | 667.54 | 885.57 |
| 480 at 32 | 3668.15 | 4985.17 |

Sixfold board volume is only the nominal sample-budget comparison. Here the high-effort roots cost 3.28 times the equal-volume low-effort roots, because only the Gen5 partnership changes effort and actual solve costs vary. The quantity arm costs 1.68 times the high-effort roots; do not call these equal-CPU arms. A subsequent intermediate-volume arm can estimate the equal-CPU comparison. Root CPU and whole-record costs are both retained in the frozen plan.

Two pilot workers use two TensorFlow threads each, leaving four threads for the primary research queue. Every fit and supervisor has an exclusive nonblocking writer lock; exact optimizer state, deterministic shuffle cursor, and model state survive restarts. The initial pilot run is `runs/effort-pilot-20261110`; `scripts/run_effort_pilot.py` is the live supervisor. Deadline remains 2026-11-11 04:30 UTC.
# Effort versus volume: initial pilot

Max authorized this experiment on 2026-11-10 to guide future collection. The first screen adds 80 Gen5 boards at 192 samples, 80 at 32, or 480 at 32 to the same frozen background dataset, with a no-addition continuation control. The main belief architecture/loss experiment and its reserved confirmation pool remain unchanged.

The high-effort source is the 102 historical-opponent records retired from arena score reporting, explicitly retained for training. Canonical holdout exclusions leave 80 training boards: 39 versus Gen4b, 18 versus Gen3, 16 versus Gen2, and 7 versus Gen1. Low-effort arms use exactly the same opponent counts and six times those counts, respectively. The smaller low-effort arm is a nested subset of the larger one. Selection is a frozen hash of deal family, without outcome selection. Three of the 480 low-effort deals are passed out, giving 477 nonempty training families. Every selected record's checksum receipt and manifest identity is checked. All inherited belief and policy families are excluded from the added data. v4/v4p policy trajectories remain excluded on both sides.

Use only shared-Gen5-auction root trajectories, including swapped partnerships. Both Gen5 actors have identical belief, policy and bidder hashes. The other partnership uses the same historical bot in the two effort cohorts. This is not a randomized paired collection experiment: the cohorts were collected at different times, and high-effort versus BEN or Gen5-32 games are deliberately excluded from this first comparison. Common roots avoid confounding collection effort with unequal fork counts.

Belief uses the existing six-epoch dense continuation recipe, the same starting v5 model, and seed, with two threads for all four arms. The first fixed-epoch comparison is emitted after one epoch, before policy work. It evaluates exact two-hidden-seat conditional NLL on 769 existing development families / 26,653 eligible positions; the full composite validation pool is also retained. Full six-epoch trajectories follow.

Policy continues the promoted attention model on observed remaining-partnership-trick targets, with the frozen original background data and the corresponding pilot additions. Use two epochs, AdamW at 0.00001, batch 128, equal family weighting, and the same seed for all arms. Evaluate fixed epochs on the original 594 development families / 53,402 outcome positions. Test outcomes, including the 578 reserved families, are never prepared or scored here. This older development distribution may understate improvements in predicting stronger Gen5 continuations; future confirmation must include fresh Gen5 positions and actual play with common inference effort.

All paired SEs cluster by canonical deal and condition on these fitted models. One seed and one set of training subsets do not establish seed or dataset dispersion. Replicate promising contrasts with both independent seed fits and new board subsets as the stream grows. No automatic promotion or gathering-policy change follows this pilot.

Measured collection costs for selected records:

| Added boards | Common-root CPU seconds | Entire-record CPU seconds including forks/native rooms |
|---|---:|---:|
| 80 at 192 | 2188.33 | 2779.10 |
| 80 at 32 | 667.54 | 885.57 |
| 480 at 32 | 3668.15 | 4985.17 |

Sixfold board volume is only the nominal sample-budget comparison. Here the high-effort roots cost 3.28 times the equal-volume low-effort roots, because only the Gen5 partnership changes effort and actual solve costs vary. The quantity arm costs 1.68 times the high-effort roots; do not call these equal-CPU arms. A subsequent intermediate-volume arm can estimate the equal-CPU comparison. Root CPU and whole-record costs are both retained in the frozen plan.

Two pilot workers use two TensorFlow threads each, leaving four threads for the primary research queue. Every fit and supervisor has an exclusive nonblocking writer lock; exact optimizer state, deterministic shuffle cursor, and model state survive restarts. The initial pilot run is `runs/effort-pilot-20261110`; `scripts/run_effort_pilot.py` is the live supervisor. Deadline remains 2026-11-11 04:30 UTC.

## First fixed-epoch belief screen

Across 769 development families, high minus equal-volume low conditional NLL was +0.00000909 (family SE 0.00001222): no measurable quality advantage. High minus sixfold low volume was +0.00009024 (SE 0.00003369), provisionally favoring volume by 2.68 conditional SE. The quantity arm versus no-addition continuation was +0.00000742 (SE 0.00006129), so there is no demonstrated absolute gain from the new data after this single epoch. These are exploratory, one-seed, one-subset results; no collection recommendation or playing-strength claim follows. Policy fitting and later belief epochs continue.
