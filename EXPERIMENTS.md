# Experiments on the Azure fleet

Priorities: **high** is not interrupted for anything lower; **medium** and **low** share what high
work leaves free, medium first. "Set by" says whose priority it is. Times are UTC, 12 November 2026
unless a date is given. Ask for a change with a file in `messages/`.

| Id | Priority | Set by | What | Needs | State |
| --- | --- | --- | --- | --- | --- |
| E1 | high | Max, 02:11 | **Gen 7 arena, phase 1, the pairs without BEN**: `7s-32` against `6-32`, `5RZ32` and `1`, to 2,000 boards a pair over all collectors. Launched by the steps in `docs/gen7_candidate_2026-11-11.md` at `fe382f9` | 4 machines, about 2 hours | Running on all four since 03:02. At 03:05: 532 boards, about 4,060 an hour; 2,000 a pair expected at about 04:25. Feeds `arena-gen7-phase1-azure1-feed` to `-azure4-feed` |
| E2 | medium | Max, 02:43 ("might be medium") | **Result labels from forks.** A fork pair records what a forced card really did against the card played. Train a head on those results and score it on the newest unseen pairs against the search's own estimate of the gap. If it beats the estimate, forks are worth more of the collectors' time | 1 machine. Hours not known until the pair set is built; first guess 3 to 6 | Step 1 running since 03:06: `azure4` is copying the Gen 6 feeds' episodes at the lowest CPU and disk priority beside E1. Building the pair set and training wait for a free machine |
| E3 | medium, proposed | Operator | **Aimed forks**, if E2 says results carry signal: none from trick 7, the forced card picked by the net where the search has it close, more where a trick is worth more IMPs. Needs a collector change and a cohort of its own | 1 or 2 machines, a few hours | Waits for E2 |
| E4 | low, proposed | Operator; Max raised longer training too | **Longer training of the policy net**: 4 to 6 epochs with a decaying rate, stopped on held-out tricks given up instead of log-loss | 1 machine, 1 to 2 hours once the training set exists (E2 builds it) | Waits for E2's data |
| E5 | low, proposed | Operator | **What a better net buys the bot**: the pre-7 match's deals and seeds replayed with only the net swapped (v2 for v4), compared board by board | 1 machine, about an hour a net for 800 boards | Not started; wants a yes from Max or the director |

## Done

| Id | Set by | What | Result | Data |
| --- | --- | --- | --- | --- |
| E0 | Max, 01:28 and 02:19 | **Pre-7 test match**: `7s-32` at trust 0.25 (the candidate of 11 Nov) against `6-32`, first on `azure1`, then on all four with separate deal blocks, until the arena went to Gen 7 | 1,637 boards, no failures: +0.25 +- 0.08 IMPs a board for `7s-32` (265 won, 157 lost, 1,215 flat). `azure1`'s first 308 boards: tree audit forks -0.15 +- 0.18 IMPs a fork. Stopped at 02:52 to 02:58 for E1 | `transfer/pre7-test-azure1-20261112` to `-azure4-`; guide `docs/pre7_test_2026-11-12.md` on `feature/gen7-prepare-slice-20261112` |

## After E1

Phase 1's three pairs should reach 2,000 boards each at about 04:25 if these four machines are the
only collectors of those pairs. Then all four are free. With no other direction the operator's
default is: one machine on E2, and the other three back on `7s-32` against `6-32` test boards with
the full fork load, since Max asked for the machines to keep playing matches until told otherwise.
The director can change that default with a message.
