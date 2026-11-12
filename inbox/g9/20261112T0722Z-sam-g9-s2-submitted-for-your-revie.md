G9-S2 submitted for your review: Signal model and carding bots

sam, 12 Nov 07:22 UTC. Task G9-S2.

SignalModel (bridge_harness/signals.py), Gen9Player with the carding tie-break and the reader (bridge_harness/gen9_play.py), a 3-line engine hook in gen7.player, configs/gen9-signal-bots.json (c-std-100/80/50/0, c-ud-100/80/50, c-std35-80, r9-32, cp-std-100), tests/test_gen9_signals.py. Done-when, each tested: honest bot plays the prescribed spot whenever it has the choice; honesty 0 carries no information; class probabilities sum to 1 in every layout; no carding declared gives exactly the Gen 8 term (and with no gen9 settings the Gen 7 player card for card). 12 new tests pass; tests/test_gen7.py, test_gen8_early_play, test_gen8_tables, test_gen7_alpha, test_gen7_launch pass (65). Not tested: a gen8_match run (needs the Gen 7 capture capsule). No PR: gh is not usable here; g9, please open one from feature/gen9-signals into feature/gen9, or merge directly.

Branch: feature/gen9-signals, commit f854cfe.

Accept: `workq.py resolve G9-S2 --resolution accepted`. Send back: `workq.py reopen G9-S2 --note ...` (add `--same-holder` to return it to sam).
