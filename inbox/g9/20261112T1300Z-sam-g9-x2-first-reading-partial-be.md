G9-X2 first reading (partial bench): BEN's emission model is worth -0.003 +- 0.021 (BEN 16) and -0.041 +- 0.046 (BEN 64) tricks a board over Gen 8, for +0.25 to +0.33 nats a declarer decision

sam, 12 Nov 13:00 UTC. Task G9-X2.

From sam, 12 Nov 13:06 UTC.
The bench (p41's, snapshot at bb1cd2c, on feature/gen9-reading-bench) is solving E9-7's held-out BEN tables in the sandbox since 12:15, house bots' decisions only, pool 512, Gen 8 net v4. Scored so far: 52 BEN 16 tables (1,054 decisions, 22 deals) and 86 BEN 64 tables (1,725 decisions, 38 deals). Paired on the same solves, r9b-32 (E9-7's emission tables) against 8x-32 (net at 0.3 for BEN), tricks a board (both tables of a deal), standard errors by deal:
- BEN 16: -0.003 +- 0.021 (+0.33 nats a declarer decision, the only decisions where the two differ)
- BEN 64: -0.041 +- 0.046 (+0.25 nats)
- Gen 8 against no reading: +0.04 +- 0.05 and +0.19 +- 0.06 tricks a board; net v4 read in full (factor 1 on BEN): -0.08 +- 0.05 against Gen 8 on BEN 64 (consistent with E9-7's factor result).
Against your arithmetic (0.14 tricks a nat at a fifth of the decisions): +0.3 nats x 0.14 x (declarer decisions are 37% of these house decisions) ≈ +0.015 tricks a board. The bench cannot yet tell that from zero. On the 300 tables a version the standard error should come down to about 0.01 (BEN 16), so the question 'under 0.02?' should be answerable by about 15:00 for BEN 64 (sandbox) and by the box job for BEN 16.
E9-10: it is BEN 16 only today (two jobs, resubmitted at 12:49 on 67c59de with will's per-run tags). I have not submitted BEN 64 jobs and will not unless the full bench shows a positive effect. Registered in E9-10's log before any board: -0.01 IMPs a board, 80% interval -0.11 to +0.09. With 1,600 boards a side E9-10's own standard error will be about 0.1 to 0.15 IMPs, so it cannot see an effect of this size; you may want to cancel or shorten it and give the box time to E9-0. Your call.
Next, per your order: E9-15 (code is in, 4a82227 on feature/gen9-signals-v2; its run starts now, beside the bench's solving), then E9-14 (its run was stopped at 12:35 during the fits to give the bench the cores; extraction kept; restarts with faster fits after E9-15).
