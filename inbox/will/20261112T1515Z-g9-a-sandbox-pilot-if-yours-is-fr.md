A sandbox pilot, if yours is free: 8r-32~8p-32 (Max's leakage question), 400 boards

g9, 12 Nov 15:15 UTC.

g9, 12 Nov 15:17 UTC. Max asked at 14:53 how much our plays leak and what randomizing costs (experiment E9-16; reports/gen9-leakage-2026-11-12 on feature/gen9). The first played test is queued behind the arrival run and will not start before about 21:30. If your sandbox is idle, please run its first 400 boards now so that there is a played figure this evening: from feature/gen9 at 491c7f7, BRIDGE_DDS_CACHE= python3 scripts/gen9_match.py --source <capsule>/recovery --bots configs/gen9-proto-bots.json --pair 8r-32~8p-32 --deals 400 --seed 917 --workers 2 --out <dir> (8r-32 plays a random one of its exactly equal-best cards; 8p-32 is today's reader). Seed 917, not the box's 916, so it is a pilot and not part of the result. Log the figure under E9-16 with its standard error and the won/lost/flat counts. About two hours at 200 boards an hour.
