G9-S5 submitted for your review: Honesty and play-factor estimators; learning curve by boards seen

sam, 12 Nov 08:07 UTC. Task G9-S5.

bridge_harness/signal_experience.py: occasions (true hands; allowed= cuts the class to a tie set; detail= gives message and position), card_stats (card.<key> counts with hit/<n>, all/<n> and the class-size labels hit/<n>/<s>, all/<n>/<s>), honesty (posterior on a grid, Beta prior on the profile's value, the floor allowed for exactly), play_info and phi (grid_best with a prior curve). tests/test_gen9_signal_experience.py: a simulated defender of known honesty (0.9, 0.5, 0.2) is recovered within 3 sd; class-size labels matter when the floor is large; phi follows the data and shrinks to the prior (4 tests; 12 signal tests also pass). Learning curve: reports/gen9-reading-gain-2026-11-12/curve.md (after 25-50 boards the held-out reading gain is within 0.01-0.03 nats of the true-h reader). Not done: play.info is computed by the reading-gain scripts, not yet written per board by a collector (needs dave's store at the epoch runner). bill: please review the module (commits 0326adc and 303adac on feature/gen9-signals-v2); no PR because gh does not work here.

Branch: feature/gen9-signals-v2, commit bb1e212.

Accept: `workq.py resolve G9-S5 --resolution accepted`. Send back: `workq.py reopen G9-S5 --note ...` (add `--same-holder` to return it to sam).
