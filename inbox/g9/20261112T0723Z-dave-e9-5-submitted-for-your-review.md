E9-5 submitted for your review: Arena simulator: schedule and promotion rule against fixed pairs

dave, 12 Nov 07:23 UTC. Task E9-5.

Result filled in the file. PR #17. Betting test holds its level (1.5-3.5%) and futility guarantee (4.7-7.7%) under the real tails; proposals: d = 0.1, cap >= 10,000, show the betting state instead of the asymptotic interval (which disagrees with 64-79% of promotions), flag out-of-line pairs by their leave-one-out residual (a single real pair effect is covered 67%).

Branch: feature/gen9-arena-sim, commit bd1b81b.

Accept: `workq.py resolve E9-5 --resolution accepted`. Send back: `workq.py reopen E9-5 --note ...` (add `--same-holder` to return it to dave).
