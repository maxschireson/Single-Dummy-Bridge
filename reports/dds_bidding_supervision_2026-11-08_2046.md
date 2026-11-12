# DDS bidding supervision — 8 November 2026, 20:46 UTC

The saved run was found stopped at 11,408 committed training pairs. The last
event was a completed DDS batch at 20:31:39 UTC; at 20:41:27 UTC the worker
lock was free. The log contained no Python exception or cooperative pause.
This is the third unexplained interruption observed in this campaign, after
the earlier stops at 5,632 and 8,064 pairs. The cause remains unestablished.

The worker resumed from the existing model, Adam state and DDS cache at about
20:41 UTC with a 1,200-second cooperative budget. By 20:46:20 UTC it had
committed 13,328 training pairs (26,656 training auctions), up 1,920 pairs
and 15 PPO updates. Persisted active time rose from 1,945.27 to 2,223.64
seconds; wall time for this observed window was about five minutes. Active
time excludes downtime and may omit interrupted, uncommitted work.
The first eleven resumed batches spent 166.75 seconds in DDS, 10.78 in
auctions and 22.80 in updates: about 83% of those measured phases was DDS.

No configuration, source, split, or promotion gate changed. This remains
attempt 1, training toward the 50,000-pair screen, with zero promotions.
The completed 10k screen remains the only strength measurement:
-0.003 IMP per paired board, descriptive 95% interval [-0.0953, +0.0893],
on 1,000 development pairs. It failed the screen; no confirmation ran.
See [the evaluation report](dds_bidding_10000_2026-11-08.md).

A verified hot recovery archive was saved at 12,688 committed training pairs,
including model/Adam state and a consistent DDS cache, replacing the existing
recovery file. The separate exact 10k milestone archive remains preserved.
The code and training config are still the implementation published at
bdc21cb6ac942191e669c04d27b99b37c4d26fab. This report changes documentation only.
