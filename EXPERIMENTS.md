# Experiments on the Azure fleet

Priorities: **high** is not interrupted for anything lower; **medium** and **low** share what high
work leaves free, medium first. "Set by" says whose priority it is. Times are UTC, 12 November 2026
unless a date is given. Ask for a change on the board (`BOARD.md`, branch `box/coordination`).

| Id | Priority | Set by | What | Needs | State |
| --- | --- | --- | --- | --- | --- |
| E1 | closed | Max, 02:11; closed by Max, 04:09 | **Gen 7 arena, phase 1, the pairs without BEN**: `7s-32` against `6-32`, `5RZ32` and `1` | 4 machines | **Stopped for good on Azure**: 2,985 boards, no failures (828, 608, 720 and 829 a box). Max stopped the Gen 5 and Gen 1 pairs at 04:09 ("it's clear enough": +1.11 +- 0.12 and +2.19 +- 0.13 over about 1,218 boards each, all collectors). The Gen 6 pair continues in E1c. Feeds `arena-gen7-phase1-azure1-feed` to `-azure4-feed` |
| E1b | closed for 7.0 | Max, 03:20 and 03:26; superseded by E1d at 06:00 | **Phase 1, the BEN pairs, Gen 7.0** | 2 machines | Finished at 06:00 when Gen 7.1 replaced Gen 7. All collectors: BEN (16) 1,274 boards, +0.09 +- 0.12 IMPs a board for `7s-32`; BEN (64) 684 boards, +0.07 +- 0.15. Azure's share: 1,195 and 606 boards, 16 feeds |
| E1c | closed | Max, 04:09; superseded by E1d at 06:00 | **Gen 7.0 self-play in place of the Gen 5 and Gen 1 pairs** | | The source was built for it (`feature/gen7-selfplay-20261112`: the collector accepts a bot playing itself; gap forks recorded). Azure played 15 trial boards; Codex and the independent collector played about 500 self-play boards before Gen 7.1 |
| E1d | high | Max, 05:42 and 05:54 | **Gen 7.1** (policy net v4.1 in the Gen 7 bot, id `71s-32`): 7.1 against 7.0 for at least 1,000 boards and until a 95% lead, then 7.1 self-play; 7.1 in every other pair | `azure2`: `71s-32~7s-32` on every board. `azure3`: `71s-32~ben64`, eight lanes | Running. The first cohorts (06:06) played only deals from families v4.1 was trained on (the pools are shards of the independent collector's Gen 6 self-play cohort) and were closed at 06:32 to 06:39: 165, 3 and 225 boards, not evidence. Since 06:36 and 06:42 the cohorts leave out the 32,205 training families (`--exclude-families`, source `a588e09`): 1,465 deals on `azure2`, 2,933 on `azure3`. Gate at 06:47 (one board a family, all collectors): 177 boards, -0.169, 95% interval -0.547 to +0.208. |
| E3 | low, proposed | Operator | **Aimed forks**. E2 found that fork results add almost nothing to the search's own gap as labels, so this drops to low. Was: if E2 says results carry signal: none from trick 7, the forced card picked by the net where the search has it close, more where a trick is worth more IMPs. Needs a collector change and a cohort of its own | 1 or 2 machines, a few hours | Waits for E2. Note of 04:45: Azure and Codex phase 1 records have no gap forks at all (the launch source ignores the setting); E1c's cohorts have them |
| E4 | low, proposed | Operator; Max raised longer training too | **Longer training of the policy net**: 4 to 6 epochs with a decaying rate, stopped on held-out tricks given up instead of log-loss | 1 machine, 1 to 2 hours once the training set exists (E2 builds it) | Waits for E2's data |
| E5 | low, proposed | Operator | **What a better net buys the bot**: the pre-7 match's deals and seeds replayed with only the net swapped (v2 for v4), compared board by board | 1 machine, about an hour a net for 800 boards | Not started; wants a yes from Max or the director |

## Done

| Id | Set by | What | Result | Data |
| --- | --- | --- | --- | --- |
| E0 | Max, 01:28 and 02:19 | **Pre-7 test match**: `7s-32` at trust 0.25 (the candidate of 11 Nov) against `6-32`, first on `azure1`, then on all four with separate deal blocks, until the arena went to Gen 7 | 1,637 boards, no failures: +0.25 +- 0.08 IMPs a board for `7s-32` (265 won, 157 lost, 1,215 flat). `azure1`'s first 308 boards: tree audit forks -0.15 +- 0.18 IMPs a fork. Stopped at 02:52 to 02:58 for E1 | `transfer/pre7-test-azure1-20261112` to `-azure4-`; guide `docs/pre7_test_2026-11-12.md` on `feature/gen7-prepare-slice-20261112` |
| E2 | Max, 02:43; done by the policy 4.1 session | **Result labels from forks**: a head trained on what forced cards really did, scored against the search's own estimate of the gap | It does not beat the search's gap. On 7,247 unseen gap-fork pairs, with net v4.1 frozen and a head fitted on 722,589 fork results: squared error 0.566 for the head alone, 0.477 for the search's gap with a fitted slope, 0.474 for the two together (board, 05:28) | `transfer/gen7-policy-v4.1-20261112`, folder `training/policy-v4.1-20261112/`; pairs in `data/pairsA.npz` on `transfer/gen7-policy-v4.1-box-20261112` |

## Next

When the rule for `71s-32~7s-32` is met, `configs/round71-selfplay.json` is opened and `azure2`'s
cohort is replaced by 7.1 self-play. If it is not met by 1,000 boards, it is Max's call.
