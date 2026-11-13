Gen 9 is postponed in favor of 8X (Max, 00:04 UTC): finish what is in flight, start no new Gen 9 experiment, hold for 8X tasks

g9, 13 Nov 00:11 UTC.

Gen 9 is postponed in favor of 8X (Max, 00:04 UTC): finish what is in flight, start no new Gen 9 experiment, hold for 8X tasks

g9, 13 Nov 00:16 UTC.

**What 8X is** (Max to the plan session, 12 Nov 23:39 to 23:52): (1) a rollout net trained on all Gen 7+ play (building on azure2 now, `training/rollout-net-v1-20261113` on `research/plan-leverage-g8-20261112`); (2) an 8X bot with single-dummy winning-line logic to about trick 10 (declarer never gives away a made contract; a defender minimizes the chance of handing declarer a claim), full rollouts on that net as broadly as calibration allows, PIMC only when needed, inside-rollout data captured; (3) play, retrain the rollout net, repeat; (4) always a diverse population, so it does not just exploit itself. The plan session owns the engine.

**What Max asked of us:** achieve what Gen 9 was for while incorporating 8X. My reading, posted to plan on the board (00:14) as an offer it may accept or change:
- the player model becomes 8X's opponent model: in the rollouts as well as in the reading (sam's BEN head and signal models; bill's card reading for systems we hold no net for);
- dave's registry, epochs, ratings and promotion test become the loop's harness, with a fixed outside panel each generation;
- sam's bench grades each rollout net and setting before box time;
- will's queue runs the jobs with full records kept;
- randomizing among exactly equal cards becomes 8X's default if the two leakage matches show no played cost.

**Now:**
- **Everyone:** finish and write up what is in flight; start no new Gen 9 experiment; do not edit `plan_player.py`, `plan_rollout.py` or `claims.py`. I post 8X tasks when plan answers.
- **dave:** the arrival run's page when it ends (about 01:00; still the integrated test of the player model, worth reading); E9-17's t-random and its submission.
- **sam:** E9-16's readings in flight; I merge PR #30's G9-X2 parts.
- **will:** after the arrival run azure4 runs only `e9-0-n02`, `e9-0-n02e` (to 800) and `e9-16-r-v-p`, `e9-16-r-v-x`; every other Gen 9 job is cancelled (retry restarts them later). Then azure4 is released on the board. Keep full records on for anything that runs.
- **bill:** nothing new while you are away.
