G9-D7 submitted for your review: Experience pipeline in the epoch runner

dave, 12 Nov 09:13 UTC. Task G9-D7.

PR #29 (contains bill's PR #26 branch and sam's feature/gen9-signals-v2, both unmerged). bridge_harness/arena9_pipeline.py: arrival (arrive with matrix or computed distances), deltas from finished records (bill's bidding_delta with profile evidence to the bidder; sam's card_delta to the card player), the models a Gen 9 bot is handed with the epoch snapshot, trace digests, per-epoch experience report with its snapshot check. Done-when, on the rehearsal (transfer/gen9-arrival-rehearsal-20261112): epoch 3's snapshot equals the merge of exactly epochs 1-2's envelopes; the reader's honesty for guest-a is what those boards say (0.694, truth 0.8; prior 0.5) and its off-card counts are epoch 2's; rows and manifests name the snapshot; an epoch-3 floor board replays card for card (same trace, same manifest identity). Tests: 11 in tests/test_arena9_pipeline.py. Full suite 428 passed.

Branch: feature/gen9-arena-arrival, commit da4f51f.

Accept: `workq.py resolve G9-D7 --resolution accepted`. Send back: `workq.py reopen G9-D7 --note ...` (add `--same-holder` to return it to dave).
