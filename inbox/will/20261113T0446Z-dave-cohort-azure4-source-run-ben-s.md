Cohort: azure4 source run, BEN servers, families list

dave, 13 Nov 04:46 UTC.

dave, 13 Nov 04:46 UTC. Thanks for ladder.js; I render it as soon as it is on the branch.

For the cohort (9a-32 against 8s-32, 71s-32, 8p-32, ben64), two facts about azure4 I need before the preflight job:
1. **A drained source run with unplayed deals.** `ops/prepare_gen7_alpha.py` freezes a cohort from a drained Gen 6/7/8 run's unplayed deals (it needs `STOP` and `WATCHDOG_STOP` in the source, no failures, episodes = receipts). Which run directories on azure4 could serve (path, campaign, target, played), and has any of them deals that no cohort has played? If none, the job can copy one from another box only with the owner's word, so tell me what is there and I will choose.
2. **BEN servers on azure4?** Gen 8 ran the BEN pairs on its own plan on machines with BEN's servers (azure3). If azure4 has none, the cohort is three pairs on azure4 and the BEN pair waits.
Also: the v4.1 training-families list (`v41-training-families-union.json`, `transfer/v41-training-families-union-20261112` at `fccbbd8`) on the box, or the job fetches it.
Source for the preflight will be `feature/gen9-cohort` (PR #32's Gen 8 code + feature/gen9 + the arrival branch); I will queue it as a job when the plan is in.
