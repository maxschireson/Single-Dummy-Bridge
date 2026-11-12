# Experiments on the Azure fleet

Priorities: **high** is not interrupted for anything lower; **medium** and **low** share what high
work leaves free, medium first. "Set by" says whose priority it is. Times are UTC, 12 November 2026
unless a date is given. Ask for a change on the board (`BOARD.md`, branch `box/coordination`).

| Id | Priority | Set by | What | Needs | State |
| --- | --- | --- | --- | --- | --- |
| E1 | high | Max, 02:11 | **Gen 7 arena, phase 1, the pairs without BEN**: `7s-32` against `6-32`, `5RZ32` and `1`, to 2,000 boards a pair over all collectors. Launched by the steps in `docs/gen7_candidate_2026-11-11.md` at `fe382f9` | 4 machines | **Paused on all four boxes.** 2,985 boards from Azure, no failures. `azure2` and `azure3` left at about 03:45 and 03:50 for E1b; the Gen 8 session drained `azure1` and `azure4` at 03:50. All collectors together at 03:54: 1,153, 1,154 and 1,151 boards a pair; the others add about 200 to 235 an hour a pair. Resumes on a box when the Gen 8 session releases it. Feeds `arena-gen7-phase1-azure1-feed` to `-azure4-feed` |
| E1b | high | Max, 03:20 and 03:26 | **Phase 1, the BEN pairs**: one box plays `7s-32` against BEN (16), another against BEN (64), to 2,000 boards a pair over all collectors | 2 machines; about 3.5 hours for BEN (16) and 6 to 7 for BEN (64) at the first rates | Running: `azure2` BEN (16) since 03:45, about 550 boards an hour; `azure3` BEN (64) since 03:50, 250 to 310 an hour so far. Eight lanes a box. 16 feeds, listed on the board for the dashboard |
| E2 | medium | Max, 02:43 ("might be medium") | **Result labels from forks.** A fork pair records what a forced card really did against the card played. Train a head on those results and score it on the newest unseen pairs against the search's own estimate of the gap. If it beats the estimate, forks are worth more of the collectors' time | 1 machine | **Taken over by the policy 4.1 session** (board, 03:50): it builds the fork-pair set and trains a result head on its temporary box, results to `transfer/gen7-policy-v4.1-20261112`. The operator builds no second pair set. Step 1's copy of the Gen 6 feeds is on `azure4`, `~/work/feeds` (13 GB) |
| E3 | medium, proposed | Operator | **Aimed forks**, if E2 says results carry signal: none from trick 7, the forced card picked by the net where the search has it close, more where a trick is worth more IMPs. Needs a collector change and a cohort of its own | 1 or 2 machines, a few hours | Waits for E2 |
| E4 | low, proposed | Operator; Max raised longer training too | **Longer training of the policy net**: 4 to 6 epochs with a decaying rate, stopped on held-out tricks given up instead of log-loss | 1 machine, 1 to 2 hours once the training set exists (E2 builds it) | Waits for E2's data |
| E5 | low, proposed | Operator | **What a better net buys the bot**: the pre-7 match's deals and seeds replayed with only the net swapped (v2 for v4), compared board by board | 1 machine, about an hour a net for 800 boards | Not started; wants a yes from Max or the director |

## Done

| Id | Set by | What | Result | Data |
| --- | --- | --- | --- | --- |
| E0 | Max, 01:28 and 02:19 | **Pre-7 test match**: `7s-32` at trust 0.25 (the candidate of 11 Nov) against `6-32`, first on `azure1`, then on all four with separate deal blocks, until the arena went to Gen 7 | 1,637 boards, no failures: +0.25 +- 0.08 IMPs a board for `7s-32` (265 won, 157 lost, 1,215 flat). `azure1`'s first 308 boards: tree audit forks -0.15 +- 0.18 IMPs a fork. Stopped at 02:52 to 02:58 for E1 | `transfer/pre7-test-azure1-20261112` to `-azure4-`; guide `docs/pre7_test_2026-11-12.md` on `feature/gen7-prepare-slice-20261112` |

## After E1 and E1b

When `7s-32~ben` reaches 2,000 boards (about 07:30 at the first rates), the operator's default for
`azure2` is to move its eight lanes to BEN (64), which is the slower pair, unless Max or the board
says otherwise. When a pair's stop rule is met its lanes get a STOP file and their publishers finish.
E3 to E5 wait for a free machine and for the Gen 8 session's say.
