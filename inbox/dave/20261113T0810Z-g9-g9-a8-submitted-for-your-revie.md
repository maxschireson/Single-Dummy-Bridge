G9-A8 submitted for your review: Design note: a diverse arena as the source of self-play training

g9, 13 Nov 08:10 UTC. Task G9-A8.

All six points taken (a8a3647): (1) section 4 starts from the gain rule that runs (training 10%, promotion 30%, gain 60%); exploitation probes and robustness enter the gain rule as contrasts; training rises in steps as rules versions. (2) Redundancy needs an equivalence test (90% intervals inside +-0.1 IMPs and 5%, with your corrected board counts: about 1,700 at zero difference, 3,900 for 80% power). (3) Card play trains on both conditions, labelled by auction_source; common tables for evaluation. (4) Shrunk pair effect (cell minus prediction with t2), floors, at most doubling per epoch. (5) Randomization for new versions only; frozen members unchanged; new points or variants on the ladder. (6) Each variance figure names its data. Smaller: contention noted in section 9; the cohort named under League.

Branch: feature/gen9, commit a8a3647.

Accept: `workq.py resolve G9-A8 --resolution accepted`. Send back: `workq.py reopen G9-A8 --note ...` (add `--same-holder` to return it to g9).
