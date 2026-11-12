G9-D5 submitted for your review: Experience store: per-board deltas, merge, epoch snapshot

dave, 12 Nov 07:19 UTC. Task G9-D5.

PR #19 into feature/gen9. bridge_harness/experience_store.py: envelopes (delta unchanged plus source, completion time, occasion, epoch), merge() identical for any order, repeats counted once, conflicts refused, a replayed occasion (same family, seats and auction) counts once with the earliest winning, cut-off; epoch snapshots named by sha256, write-once, verified on load; player_snapshot() for PlayerModel. 12 tests, standard library only; 26 pass with test_gen9_player_model. Design choice to check: the duplicate unit is the occasion, not the family alone, because a player plays each deal twice on one board (once per room) and a differing native auction is a third table. Not done: file locations in the arena (G9-D4) and the estimators that write deltas (bill, sam).

Branch: feature/gen9-arena-experience, commit fee94e2.

Accept: `workq.py resolve G9-D5 --resolution accepted`. Send back: `workq.py reopen G9-D5 --note ...` (add `--same-holder` to return it to dave).
