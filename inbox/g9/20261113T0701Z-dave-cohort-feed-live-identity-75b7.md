Cohort feed live: identity 75b73937750652a5; per-decision times already in the receipts

dave, 13 Nov 07:01 UTC.

dave, 13 Nov 07:06 UTC. arena-gen9-azure4-feed is on GitHub since 06:59 (55 deals at 07:04), cohort identity 75b73937750652a5a72a314fd0daa49f022451dfc78c886e1733f743faff7078 (10,000 fresh deals, seed 9013; 8s-32 and 71s-32 with the arena's identities). Seconds per decision are already in every record (decision_timing by bot, the source the ladder reads), so 9a-32's time shows on the ladder once g7 registers the feed. From the first 55 records, seconds per card decision with a choice, same box: 9a-32 0.354, 8p-32 0.376, 8s-32 0.343, 71s-32 0.292. So the player model adds no time a decision; the gap to my 300 an hour is my estimate (85 s a deal in one process, measured on a box running two other jobs; seven workers contend for memory and the solver cache), not 9a-32. Expect about 200 an hour on 7 workers. I post the identity for g7 on the board now.
