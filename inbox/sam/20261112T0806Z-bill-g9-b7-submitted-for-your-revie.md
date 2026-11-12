G9-B7 submitted for your review: Replay reader: read a profile's calls by replaying its own bidder

bill, 12 Nov 08:06 UTC. Task G9-B7.

On PR #26 (sam reviewing the added commits). replay.py: ReplayReader (BEN-format softmax over hand types), RuleReplay, ProfileReplay/replay_factory (registry nets with sha check; rule bidder from a card's generator block). Tests: replay score equals the bidder's own softmax product (Gen 5 in test_gen9_cards; NetProfile equivalence), the shell's replay_correction equals replay minus scorer with the real Gen 6 reader on real two-hidden-hand positions (tests/test_gen9_replay.py, unittest), a profile without a held bidder changes nothing; no replay_reader key = g9's existing inert tests. Cost: 0.03 s per seat over 257 types (E9-8), once per hidden seat per board. Bots 9r/9c/9x/9u; pilot under E9-11 running (seconds per board will come from it).

Branch: feature/gen9-bidding-cards, commit 4204d2c.

Accept: `workq.py resolve G9-B7 --resolution accepted`. Send back: `workq.py reopen G9-B7 --note ...` (add `--same-holder` to return it to bill).
