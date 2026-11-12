# Gen 9 signals and card-play reading: results so far

> sam, 12 November 2026, 09:10 UTC. Work in progress; for the review package (G9-A6). Nothing here is
> adopted into an arena bot. Every number names its report; prediction evidence unless it says played boards.

## What was built

- **Signals as executable rules** (`bridge_harness/signals.py`). Situations come from public play. A
  carding descriptor gives the fact each signal states (count, attitude, suit preference, Lavinthal,
  odd-even), the spot rules and the lead conventions. One probability function serves the carding bot
  and the reader. Two noise models: symmetric honesty, and per-signal emission tables for asymmetric
  players (BEN).
- **Carding bots and the reader** (`bridge_harness/gen9_play.py`, folded under g9's shell as
  `SignalPlayer`). A bot signals among its search's tied cards. A reader splits each hidden play into
  the net's class term (what was done, times phi) and the signal term (which spot). With no carding
  declared it is exactly Gen 8.
- **Experience** (`bridge_harness/signal_experience.py`). From finished boards: per-signal hit
  counts (honesty) and position counts (emission tables), estimators with shrinkage, and
  `card_delta`, one call per board for the pipeline. The reader learns an unstated honesty and,
  after 200 occasions, emission tables.

## What was measured

| Question | Answer | Report |
| --- | --- | --- |
| Are spots nine and below equivalent enough to be the class? | Yes: they differ on the true deal in 1.49% ± 0.08% of 21,057 defender decisions | `reports/gen9-spot-equivalence-2026-11-12` (E9-3) |
| Do the house bots signal? | No: every association of spot with fact within ±0.12; lowest spot 60% of the time; leads fourth best about half the time | `reports/gen9-house-carding-2026-11-12` (E9-9) |
| What is reading a declared scheme worth? | +0.49 to +0.96 nats of the true layout per declarer decision over Gen 8, honesty 0.5 to 1; the facts' share rises with honesty | `reports/gen9-reading-gain-2026-11-12` (E9-4 part 1) |
| What does a wrong honesty cost? | Too high: up to 0.86 nats lost. Too low: at most 0.12. So the prior is 0.5 | same |
| How fast is honesty learned? | Within 25 to 50 boards of experience, to within 0.01 to 0.03 nats of the true-h reading | `.../curve.md` |
| Should honesty be carried as a grid? | Only before any experience (+0.01 to +0.05 nats); not after 5 to 10 boards | `.../grid_vs_point.md` |
| What would designed signals give the house defence? | +0.13 nats per defender decision, and +0.32 leaked to a declarer who knows them; count carries most of both | `reports/gen9-signal-pair-2026-11-12` (E9-6 part 1) |
| Does BEN signal, and can we read it? | Yes, count from a low-card default. An emission model fitted on held-out deal families reads BEN's defenders +0.16 to +0.32 nats per decision better than Gen 8 | `reports/gen9-ben-reading-2026-11-12` (E9-7) |

## What is not known yet

- **IMPs.** Every reading number above is nats of the true layout's weight. E9-0 (g9) converts nats to
  IMPs. Played boards are queued on azure4: E9-4 part 2 (the reader against carding bots, same deals,
  with and without it), E9-6 part 2 (designed signals against a declarer who knows them). E9-4 is also
  running in the sandbox on independent deals.
- **Whether designed signals help the house in play.** In nats they leak more than they inform; the
  match against `r9p-32` decides it.
- **BEN in play:** E9-10 uses the fitted model (`configs/carding/ben16.json`, `ben64.json`, bot `r9b-32`)
  and needs BEN lanes on a box.
- **Not built:** continuations of a signal on later rounds, Smith echo, per-strain signal fields, a
  learned per-player vector in the policy net, an adapter for BEN's card choices.
