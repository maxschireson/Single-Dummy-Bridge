# E9-6 on the reading bench: what designed signals give the house pair, and what they give away

Gen 9 research (sam, signals), 12 November 2026. Experiment file: `experiments/E9-6.md` on `team/gen9`.
Kind of evidence: **prediction** (double-dummy tricks saved on stored solves; no match). Nothing adopted.

**Method.** E9-4 part 1's 296 usable house tables (`arena-gen7-phase1-azure1-feed` at f9dad79), the defenders' spots
and opening leads drawn again by the standard scheme at honesty 1 (`scripts/gen9_reading_bench.py relabel`, E9-4's
seeds), every decision of every seat after the opening lead solved again (12,029 decisions, 135 deals; pool 512, net
v4). Readings: `base` = 8p-32 (the net in full on every seat's cards); `pair` = cp-std-100 (the same, with partner's
spots read by the scheme: the defenders who signal reading each other); `decl` = r9p-32 told the scheme (the opposing
declarer reading the signals). A board is one table; standard errors by deal.

## Result

Tricks a board, paired against `base`; the bench's nats beside:

| | Tricks a board | Nats a decision of that side |
| --- | ---: | ---: |
| Defenders reading each other's signals (`pair`, defender decisions) | +0.018 ± 0.015 | +0.39 |
| Declarer told the scheme (`decl`, declarer decisions) | +0.072 ± 0.031 | +1.06 |
| Net, against a declarer who knows the scheme | -0.054 ± about 0.034 (errors combined as if independent) | |

- Signals at honesty 1 give the defending pair +0.018 ± 0.015 tricks a board and a declarer who knows the scheme
  +0.072 ± 0.031: they give away about four times what they inform, about -0.19 IMPs a board net.
- This repeats E9-6 part 1 in tricks: there, +0.13 nats a defender decision against +0.32 leaked.
- Not measured: what the signals cost against a declarer who does not know the scheme (8p-32 reading the
  relabelled spots with the house net). That needs the same tables solved without relabelling.

**Limits.** Nobody reacts to the signals in the recorded play: the bench scores each decision's card choice under each
reading, so a defence that would play differently after reading partner is credited only through the cards it
chooses at each decision. The signals follow the house bots' recorded play elsewhere.
