G9-S1 (signals design note) and G9-S3 (E9-3) are submitted for your review; I have leased G9-S2 and started it.

From sam, 12 Nov.

- **Note:** `docs/gen9/signals.md` on `feature/gen9-signals-design` at `f1016e0`, 173 lines.
- **E9-3:** result in `experiments/E9-3.md`; data and code on `research/gen9-spot-equivalence` at `0838808`. Defenders' spots differ on the true deal in 1.49% ± 0.08% of 21,057 decisions, so the class rule stands for v1. Exceptions: top spot a nine (2.8%), trumps (3.2%), ruffs (7.3%), no outstanding card above the top spot (5.0%).
- **For the carding bot:** the search's tie set holds the whole class in 91.5% of defender spot plays. Where it does, the spots differ on the true deal 0.10% of the time; where it doesn't, 15.5%. So the bot signals only among ties.

**Two interface additions for you to accept or refuse** (both marked in the note):
1. I5: add `play_log_terms(o, view, assign, plays) -> (net_part, signal_part)` beside `play_log_likelihood`, so your player shell (G9-A3) can apply `play_weight` to the net part only. The signal part is a calibrated likelihood; 8s-32's exponent of 0.5 was fitted for the net. Until you say otherwise I build both, and `play_log_likelihood` returns their sum.
2. Experience: next to your `hit/<n>` and `all/<n>` on `card.<k>`, also `hit/<n>/<s>` and `all/<n>/<s>` (`s` = class size). The reader's floor `eps` puts `eps/s` on every spot, so the aggregate labels read `h` low by about `eps`. `choice_honesty` keeps working on the aggregates; I add an exact estimator beside it in G9-S5.

**E9-4 part 1 without a box** (note, section 6): re-choose the defenders' spots on recorded boards by the carding bot's rule, within the recorded tie set, and swap the order of play of the two cards. A swap is kept only if every trick's winner is unchanged. That gives exact carding-bot spot play on real deals for every scheme × honesty cell in the sandbox. Part 2 (played boards) still needs a box. Tell me if you object; otherwise I do part 1 this way after G9-S2.
