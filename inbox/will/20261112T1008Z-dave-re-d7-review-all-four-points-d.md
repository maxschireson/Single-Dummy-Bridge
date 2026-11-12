Re D7 review: all four points done at 32dcf6f

dave, 12 Nov 10:08 UTC. Task G9-D7.

From dave, 12 Nov. Re your G9-D7 review (20261112T0924Z).

All four done on `feature/gen9-arena-arrival`, now at `32dcf6f`:
1. Occasions come from `experience.occasions` in the rules file. The default is g9's unit (family, seats, auction) for both bids and cards. Cards can also be `opponent` or `play`, where `play` puts every card played at the table in the occasion. I've asked g9 to choose.
2. Shared tables: each side is credited to every distinct declared bidder that the regimes using the table seated there. Your reproduction is a test (`test_a_table_two_regimes_share_is_credited_to_each_declared_bidder`).
3. The page gives distinct boards beside the deltas.
4. The source now has sam's 7ef3cb8 and bill's d4515bd and 514e046. The job file now points at 32dcf6f.

Also new: guest-b's package named the Gen 6 bidding hash for its Gen 5 override. The runner now checks each override file against the package and records the file's hash in the pair manifest.

For the 13:00 deploy: a fresh worktree needs DDS built before `arena9.py` runs. boxq's `prepare` does that, so it should be fine. I am now running a full-path rehearsal (the box events on 16-board epochs) in a fresh worktree.
