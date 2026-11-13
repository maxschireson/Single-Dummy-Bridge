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
| Both on the relabelled tables: partner's gain less a told declarer's | -0.054 ± about 0.034 (errors combined as if independent) | |

- On the relabelled tables, signals at honesty 1 give the defending pair +0.018 ± 0.015 tricks a board and a
  declarer who knows the scheme +0.072 ± 0.031 over the house net's reading of the same cards: they give away about
  four times what they inform. What a match would show also depends on how the signals change the opponents'
  reading of them with the house net; see below.
- This repeats E9-6 part 1 in tricks: there, +0.13 nats a defender decision against +0.32 leaked.
## Against a declarer who does not know the scheme: the same tables as played

The same 296 tables solved again as they were played (no relabelling; every decider; 12,029 decisions). Tricks a
board saved by each side's reading against no reading:

| | As played (house spots) | Relabelled at std-100 |
| --- | ---: | ---: |
| Declarer, the net in full (8p-32) | +0.093 ± 0.024 | +0.049 ± 0.025 |
| Declarer told the scheme (r9p-32) | | +0.122 ± 0.037 |
| Defenders, the net in full (8p-32) | +0.084 ± 0.024 | +0.082 ± 0.026 |
| Defenders reading each other by the scheme (cp-std-100) | | +0.100 ± 0.028 |

- The signals cost a declarer who reads them with the house net 0.044 tricks a board (+0.049 against +0.093): the
  net expects the house bots' own spot habits and misreads the signals.
- In a duplicate match the signalling pair A against a pair B, at the table where A defends and the table where A
  declares: A's margin = (A's defence − B's defence) + (A's declarer − B's declarer), each a reading's saving.
  - B = 8p-32 (match 1, `e9-6-vs-8p`): (0.100 − 0.084) + (0.093 − 0.049) = **+0.060 tricks a board, about +0.22 IMPs**.
  - B = r9p-32, told the scheme (match 2, `e9-6-vs-reader`): (0.100 − 0.084) + (0.093 − 0.122) = **-0.013, about
    -0.05 IMPs**.
  These combine figures from two sets of solves of the same deals; their errors, taken as independent, are about
  ±0.05 tricks a board, and the deals' correlation makes the true error smaller.

**Limits.** Nobody reacts to the signals in the recorded play: the bench scores each decision's card choice under each
reading, so a defence that would play differently after reading partner is credited only through the cards it
chooses at each decision. The signals follow the house bots' recorded play elsewhere.
