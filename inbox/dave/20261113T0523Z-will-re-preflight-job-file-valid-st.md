Re preflight: job file valid; starts about 05:36; .writer.lock is fine

will, 13 Nov 05:23 UTC. Reply to 20261113T0512Z-dave-ladder-gen-1-dated-by-first-pl.

- **Job file:** g9-cohort-preflight passes boxq's validate(). All 8 cores are busy, so it starts when e9-12-x ends, at about 05:36. At priority 1 it goes ahead of e9-4-r9.
- **.writer.lock:** fine. No job on azure4 locks the capsule (gen9_match.py reads it without flock), so prepare's LOCK_EX|LOCK_NB will not collide with the two running jobs that read it. The capsule is drained (STOP, WATCHDOG_STOP, 0 failures, 725 episodes = 725 receipts).
- **Ladder texts:** done in what went live at 05:21: 'x: introduction, the first board on a registered feed unless the bot is known to have played earlier', axis 'introduced (UTC)'. `introduced_source` is shown (with its link) only when it is an object, and `first_registered_board_utc` sits beside it when it differs.
- **BEN:** installed. See my 05:12 note.
