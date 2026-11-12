# E9-6 part 1: what designed signals are worth to the house defence, and what they leak

Gen 9 research (sam, signals), 12 November 2026. Experiment file: `experiments/E9-6.md` on `team/gen9`.
Kind of evidence: **prediction** (gain in the true layout's log weight). Nothing adopted.

**Method.** `scripts/gen9_signal_pair_gain.py` (report: `scripts/gen9_signal_pair_report.py`) on the
first 150 main tables of `arena-gen7-phase1-azure1-feed` (Gen 7 house bots). Each table is replayed as
recorded and with both defenders' spots and opening leads re-chosen by a scheme at honesty 1 within the
recorded tie sets (as E9-4 part 1). At the same plies of the two games, tricks 1 to 6, the house player's
reading of the hidden plays is scored against a pool of 256 auction-weighted layouts. "Today" is the
recorded spots read by the house net in full. Columns are the gain over today in nats per decision
(1,399 defender and 1,555 declarer decisions per cell), standard errors clustered by table.

| Signals | Partner reads them (defender decisions) | A declarer who knows the scheme (the leak) | A declarer reading with the house net |
| --- | ---: | ---: | ---: |
| All (fourth-best leads, attitude on partner's lead, count on declarer's, attitude discards) | +0.130 ± 0.056 | +0.317 ± 0.107 | -0.729 ± 0.078 |
| Attitude on partner's lead only | +0.031 ± 0.031 | +0.030 ± 0.045 | -0.335 ± 0.050 |
| Count on declarer's lead only | +0.065 ± 0.026 | +0.179 ± 0.047 | -0.241 ± 0.043 |
| Attitude discards only | -0.009 ± 0.020 | -0.037 ± 0.030 | -0.153 ± 0.031 |
| Fourth-best leads only | -0.018 ± 0.045 | -0.039 ± 0.077 | -0.387 ± 0.063 |

- **The house defence gains +0.13 nats per defender decision from designed signals; a declarer who
  knows the scheme gains +0.32 per declarer decision from the same cards.** In nats the leak is the
  larger of the two. Which matters more in IMPs is for E9-0's exchange rate and for part 2 to say.
- **Count carries most of both** (defence +0.065 ± 0.026, leak +0.18 ± 0.05). Attitude alone is small
  on both sides (+0.03 ± 0.03 for the defence, +0.03 ± 0.05 leaked), so its ratio is not known yet;
  it is the candidate for the cheapest signal to give. Attitude discards and conventional leads add
  nothing over today's house reading. The house net already reads the house bots' own lead habit
  (E9-9: fourth best about half the time).
- **A declarer who reads these spots with the house net in full is misled:** -0.73 nats per decision.
  That is `8p-32`'s position in part 2's first comparison. A gain there would partly come from
  misleading an opponent who reads the signallers by house habits, not from informing partner. The
  comparison against `r9p-32` (a declarer who knows the scheme) isolates the value of the signals.

**Implication for part 2.** Run three comparisons: `cp-std-100~8p-32`, `cp-std-100~r9p-32`, and an
attitude-only pair `cp-att-100~r9p-32` (the candidate for the cheapest signal relative to what it leaks).
Bot entries: `configs/gen9-signal-bots.json`.

**Limits.** Prediction evidence: partner does not act on the signals here (the recorded play stands),
and declarers' decisions stay the recorded ones. One feed, 150 tables.
