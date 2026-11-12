# Layout-selection test, tricks 1–5 (11 November 2026)

Which layouts to solve once the posterior over the hidden hands is known. Run in the Gen 6
package chat with the belief-research chat's test (`analysis/auction_belief/select_layouts.py`
on `research/joint-auction-belief-20261110`, commit 2b81ced), on recorded Gen5 common-auction
tables 326–436 (109 tables with 52 recorded cards, 1,841 non-forced decisions after the lead in
tricks 1–5).

For each decision: 256 independent posterior layouts form the pool, 256 more are held out as the
reference. Every method picks a card from the layouts it solves; its loss is the reference's best
mean double-dummy value minus the reference's value of the picked card. All methods use the same
posterior (hand-type classes weighted by a hand-fit scorer), so this measures layout choice only.

| Method | Layouts solved | Loss, tricks per table | Against 32 plain picks |
| --- | --- | --- | --- |
| Plain independent picks | 32 | 0.073 ± 0.011 | |
| Evenly spaced through the cumulative class weight | 32 | 0.039 ± 0.005 | +0.035 ± 0.011 |
| Cluster centres | 32 | 0.047 ± 0.006 | +0.026 ± 0.011 |
| One random member per cluster | 32 | 0.050 ± 0.005 | +0.024 ± 0.011 |
| The 32 most likely classes | 32 | 0.151 ± 0.015 | −0.078 ± 0.016 |
| Plain | 64 | 0.030 ± 0.004 | +0.043 ± 0.011 |
| Cluster centres | 64 | 0.020 ± 0.002 | |
| One per cluster | 64 | 0.025 ± 0.003 | |
| Plain | 128 | 0.017 ± 0.003 | +0.056 ± 0.011 |
| Plain | 256 | 0.009 ± 0.002 | +0.064 ± 0.011 |

Evenly spaced picks at 64 were added as an arm part-way (tables 396–436, 39 tables, 651
decisions). On those tables: evenly spaced 64 loses 0.019 ± 0.004; it beats plain 64 by
+0.020 ± 0.008, cluster centres 64 by +0.003 ± 0.006, one per cluster 64 by +0.008 ± 0.007 and
evenly spaced 32 by +0.013 ± 0.008 (+0.005 ± 0.004 in tricks 1–2, +0.009 ± 0.006 in tricks 3–5);
plain 128 is +0.002 ± 0.006 better and plain 256 +0.010 ± 0.004 better.

At 32, one per cluster is 0.011 ± 0.006 behind evenly spaced. Clusters: k-medoids on one hidden
hand's unseen cards weighted by rank plus its suit lengths, L1 distance.

Limits: the scorer here was a copy of the hand-fit scorer stopped after 7 of its 22 training
minutes (SHA-256 `ed369c98…e2f2b7f7`, not published), not v0. Losses are against held-out posterior layouts,
not played results; levels are biased up by taking the reference's maximum, differences are not.
One run; the intervals are unadjusted across the comparisons shown.

Files: `sel_0.jsonl.gz`, `sel_1.jsonl.gz` (one line per table), `select_layouts.py` (the test as
run here: the research branch's script plus the evenly-spaced-64 arm; it needs that branch's
`classes.py`, `play_classes.py`, `late_play.py`, `nbid.py` and a scorer file), `summary.py`
(reproduces `results.txt` from the records, NumPy only), `results.txt`.
