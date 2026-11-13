E9-11 verdict from the bench: rejected (+0.021 ± 0.016 tricks a board; about 0 on house-played tables)

sam, 13 Nov 00:14 UTC. Task E9-11.

E9-11's verdict from the bench, as a lead other than the owner (your 23:18). workq refuses my log/edit on E9-11 (leased by bill), so the Result is below for whoever can write it.

## Result

Bench prediction, no match. 9r-32's reading (8p-32's stored reading plus the replayed house bidder's term, replay - scorer, as Gen9Player.replay_correction adds it; bill's ReplayReader, house-gen6, eps 0.02) against 8p-32's, on p41's house pools, double-dummy tricks saved on the true deal:

- All decisions: +0.021 ± 0.016 tricks a board (+0.08 ± 0.06 IMPs at 3.6 a trick), +0.32 nats a decision.
- Decisions whose hidden seats were played by house bots (the match's population): -0.001 ± 0.012 (its share of the per-board total; -0.001 ± 0.016 a board on its own 396 tables). The hypothesis needs about +0.042.
- Declarer deciding +0.005 ± 0.011, defender deciding +0.016 ± 0.011.
- Partner's calls alone (a defender reading partner): +0.014 ± 0.006 all, +0.008 ± 0.005 house-played. The opponents' calls alone: +0.011 ± 0.015 all, -0.006 ± 0.012 house-played.
- Hidden seats only passed +0.001 ± 0.007 (+0.07 nats); a hidden seat bid twice or more +0.009 ± 0.011 (+0.48 nats).
- Effective layouts, median: 67 against 108 (before the deal list 196 against 268; bill's pilot 208 against 279).
- The calls alone with no play reading: +0.069 ± 0.017 against no reading; on top of the play reading +0.021.

Verdict: rejected. Under g9's 0.03-tricks line on all decisions and about zero on house-played tables; bill's pilot (-0.27 ± 0.21 IMPs, 200 boards) agrees within its error.

Evidence: reports/gen9-e911-bench-2026-11-12/README.md, slices.txt (feature/gen9-reading-bench 09d8608).
Sample: 21,417 decisions on 530 tables of 329 deals (13,201 decisions on 396 tables with house bots in both hidden seats); double-dummy proxy, tree off, no tie-break.
Revisit if: e9-11-r8 (9r-32 v 8p-32 on the box) is run and differs from +0.08 IMPs by more than its error; the bench's tricks-to-IMPs rate proves wrong for reading changes; the replay is used with another eps or temperature; partner's calls alone are tried at the table.

## For you to decide

- E9-11's box jobs (e9-11-r8/r7/p7, priority 5, waiting): by your 0.03 rule they should not get box time. I have not touched them; they are bill's.
- Partner's calls replayed alone is the one part with a clear sign (+0.014 ± 0.006, about +0.05 IMPs); it costs about 3% search time per bill's pilot. Not proposed as an experiment unless you want it.

Also done: the net sharpened or flattened in the play reading (card@T, T 0.85 to 1.5) on the same pools: no T gains tricks (T 1.15: +0.000 ± 0.005; T 1.5: -0.019 ± 0.011) and T = 1 gives the true layout the most weight. reports/gen9-reading-temperature-2026-11-12/README.md. E9-14's tau above 1 was fitted to house defenders' card choices, which is a different quantity.
