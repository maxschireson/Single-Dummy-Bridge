# Experiments on the Azure fleet

Priorities: **high** is not interrupted for anything lower; **medium** and **low** share what high
work leaves free, medium first. "Set by" says whose priority it is. Times are UTC, 12 November 2026
unless a date is given. Ask for a change on the board (`BOARD.md`, branch `box/coordination`).

| Id | Priority | Set by | What | Needs | State |
| --- | --- | --- | --- | --- | --- |
| E1 | closed | Max, 02:11; closed by Max, 04:09 | **Gen 7 arena, phase 1, the pairs without BEN**: `7s-32` against `6-32`, `5RZ32` and `1` | 4 machines | **Stopped for good on Azure**: 2,985 boards, no failures (828, 608, 720 and 829 a box). Max stopped the Gen 5 and Gen 1 pairs at 04:09 ("it's clear enough": +1.11 +- 0.12 and +2.19 +- 0.13 over about 1,218 boards each, all collectors). The Gen 6 pair continues in E1c. Feeds `arena-gen7-phase1-azure1-feed` to `-azure4-feed` |
| E1b | high | Max, 03:20 and 03:26 | **Phase 1, the BEN pairs**: one box plays `7s-32` against BEN (16), another against BEN (64), to 2,000 boards a pair over all collectors | 2 machines | Running. At 04:52, all collectors: BEN (16) 620 boards, -0.11 +- 0.17 IMPs a board, about 510 an hour; BEN (64) 331 boards, +0.11 +- 0.24, about 340 an hour. 2,000 at about 07:30 and 09:45. 16 feeds, on the dashboard since 04:17 |
| E1c | high | Max, 04:09 | **Self-play in place of the Gen 5 and Gen 1 pairs**: plan `configs/round7-phase1-selfplay.json`, `7s-32~6-32` one board in three and `7s-32~7s-32` two, on the deals the stopped phase 1 cohorts had not played | Every box that is free of E1b and of the Gen 8 session | Source built and tested: `feature/gen7-selfplay-20261112` at `7780e5e` (the collector accepts a bot playing itself; the capture port is merged, so gap forks are recorded). `azure2` holds cohort `c50412d34108` (2,202 deals), trial of nine boards, then stopped; it runs at volume when BEN (16) reaches 2,000 boards or when Max says sooner. Codex and the cloud collector use the same branch |
| E3 | low, proposed | Operator | **Aimed forks**. E2 found that fork results add almost nothing to the search's own gap as labels, so this drops to low. Was: if E2 says results carry signal: none from trick 7, the forced card picked by the net where the search has it close, more where a trick is worth more IMPs. Needs a collector change and a cohort of its own | 1 or 2 machines, a few hours | Waits for E2. Note of 04:45: Azure and Codex phase 1 records have no gap forks at all (the launch source ignores the setting); E1c's cohorts have them |
| E4 | low, proposed | Operator; Max raised longer training too | **Longer training of the policy net**: 4 to 6 epochs with a decaying rate, stopped on held-out tricks given up instead of log-loss | 1 machine, 1 to 2 hours once the training set exists (E2 builds it) | Waits for E2's data |
| E5 | low, proposed | Operator | **What a better net buys the bot**: the pre-7 match's deals and seeds replayed with only the net swapped (v2 for v4), compared board by board | 1 machine, about an hour a net for 800 boards | Not started; wants a yes from Max or the director |

## Done

| Id | Set by | What | Result | Data |
| --- | --- | --- | --- | --- |
| E0 | Max, 01:28 and 02:19 | **Pre-7 test match**: `7s-32` at trust 0.25 (the candidate of 11 Nov) against `6-32`, first on `azure1`, then on all four with separate deal blocks, until the arena went to Gen 7 | 1,637 boards, no failures: +0.25 +- 0.08 IMPs a board for `7s-32` (265 won, 157 lost, 1,215 flat). `azure1`'s first 308 boards: tree audit forks -0.15 +- 0.18 IMPs a fork. Stopped at 02:52 to 02:58 for E1 | `transfer/pre7-test-azure1-20261112` to `-azure4-`; guide `docs/pre7_test_2026-11-12.md` on `feature/gen7-prepare-slice-20261112` |
| E2 | Max, 02:43; done by the policy 4.1 session | **Result labels from forks**: a head trained on what forced cards really did, scored against the search's own estimate of the gap | It does not beat the search's gap. On 7,247 unseen gap-fork pairs, with net v4.1 frozen and a head fitted on 722,589 fork results: squared error 0.566 for the head alone, 0.477 for the search's gap with a fitted slope, 0.474 for the two together (board, 05:28) | `transfer/gen7-policy-v4.1-20261112`, folder `training/policy-v4.1-20261112/`; pairs in `data/pairsA.npz` on `transfer/gen7-policy-v4.1-box-20261112` |

## After E1b

When `7s-32~ben` reaches 2,000 boards (about 07:30), `azure2`'s eight lanes stop and its self-play
cohort (E1c) starts with eight workers, unless Max or the board says otherwise. When `7s-32~ben64`
reaches 2,000, `azure3` does the same with its own phase 1 deals. E4 and E5 wait for a free machine
and for the Gen 8 session's say.
