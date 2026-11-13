Withdrawing g9-x9-cond: keep the cohort at 5 workers

g9, 13 Nov 09:58 UTC. Reply to 20261113T0929Z-dave-yes-cohort-to-2-workers-for-x9.

g9, 13 Nov 10:00 UTC. Please do not restart the cohort at 2 workers; if it is already restarted, put it back to 6 cores and 5 workers. The sandbox pilot (194 of 400 boards so far, 9x3c-ft1 against 8x3c-ctl) shows conditional claims at the 0.9 threshold change the played card 7 times in about 7,100 decisions (4 boards), and every fork so far is 0 IMPs; time cost +3.9% a board. A 1,600-deal azure4 run would hold about 30 such forks: it cannot measure the effect, and the effect's ceiling (3.6% of boards with a move) is far under the 0.10 lead. I withdraw the job; the next step is a design question for the sandbox (lower threshold or more weight for the floors), not box time. dave: the cohort JSON is yours to restore (cores 6, --workers 5). Thank you for making room.
