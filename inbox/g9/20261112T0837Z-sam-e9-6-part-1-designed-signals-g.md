E9-6 part 1: designed signals gain the defence +0.13 nats a decision and leak +0.32 to an aware declarer; 8p-32 is misled by them (-0.73), so test against r9p-32

sam, 12 Nov 08:37 UTC. Task E9-6.

From sam, 12 Nov. Report: `reports/gen9-signal-pair-2026-11-12/README.md` on `feature/gen9-signals-v2` at `58373d2`. Prediction evidence: 150 recorded Gen 7 tables, both defenders' spots and leads re-chosen by the scheme at honesty 1 within the recorded tie sets. Gains are nats of the true layout per decision over today's house reading.

| Signals | Partner reads them | Leak to a declarer who knows | Declarer reading with the house net |
| --- | ---: | ---: | ---: |
| All | +0.13 ± 0.06 | +0.32 ± 0.11 | -0.73 ± 0.08 |
| Count on declarer's lead only | +0.065 ± 0.026 | +0.18 ± 0.05 | -0.24 ± 0.04 |
| Attitude on partner's lead only | +0.03 ± 0.03 | +0.03 ± 0.05 | -0.34 ± 0.05 |
| Discards only, leads only | about 0 | about 0 | -0.15, -0.39 |

What it means for the box:
1. **The leak is the bigger number in nats.** Whether a defender's nat buys more IMPs than a declarer's is E9-0's question. Without it, designed honest signals look like a net loss against a declarer who reads them.
2. **`cp-std-100~8p-32` is not a clean test.** `8p-32` reads the signallers' spots with the house net in full and is misled (-0.73). A gain there would partly be an uncalibrated opponent being misled, so it shouldn't be read as the value of signals. `cp-std-100~r9p-32` isolates the signals' value. I added `cp-att-100~r9p-32` (attitude only, small on both sides).
3. **Plan:** three matches of 1,600 boards, about 4.8 box-hours (`docs/gen9/signals-runs.md`). If only two fit, the two against `r9p-32`.

Also running: E9-7. BEN signals by count with a low-card default: on declarer's lead the highest spot 21% of the time from even length, 5% from odd. The reader now has emission tables for asymmetric signallers like this (`signals.SignalModel(emission=...)`, `d8169a2`). The held-out reading gains come in about 40 minutes, then your grid-versus-point question.
