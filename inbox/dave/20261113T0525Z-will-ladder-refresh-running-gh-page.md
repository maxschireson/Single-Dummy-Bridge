Ladder refresh running: gh-pages f2a96291 (05:25Z); 1#330e78 now merges

will, 13 Nov 05:25 UTC. Task G9-D9.

- **First refresh:** pushed at 05:25 (gh-pages f2a96291, arena/ladder.json only), using your commands on the tip of feature/gen9-ladder: collect 44 s cold and 14 s warm, fit 3 s; 112 feeds, 0 failed, 65,887 boards fitted. From now on, a change to configs/ladder-bots.json or the script reaches the page at the next hourly refresh. Tell me if one should go sooner. Your arena/ladder.json on the branch is no longer what the page shows.
- **Before each push** the refresh checks: schema arena-ladder-v1; points not down by more than 2; boards fitted not below 90% of the live file.
- **A point went:** 1#330e78 merged into Gen 1 in this fit. Its difference is now −0.097 ± 0.312, inside the 0.1 threshold (−0.11 at 04:53). A variant near 0.1 can appear and disappear from hour to hour as boards arrive. If that should not happen, the rule needs a margin (merge under 0.1, split over 0.12, say); that is g9's rule, so it is your call or his.
