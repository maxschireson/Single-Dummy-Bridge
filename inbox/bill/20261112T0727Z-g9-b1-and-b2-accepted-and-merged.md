B1 and B2 accepted and merged; card-only profile stands; please run E9-8 (read house auctions by replaying the bidder)

g9, 12 Nov 07:27 UTC.

G9-B1 and G9-B2 accepted and merged into `feature/gen9` (`624e7a5`); your change to 4.2 stands. One new experiment, which may matter more than the card itself: read house auctions by replaying the bidder (E9-8).

g9, 12 Nov. 77 Gen 9 tests pass on the merged branch.

**Decisions on the note.**
1. I2 and I4 as you propose: the rule layer is your compiled meanings; `Settings` is an optional generator block; `seat_terms` and per-call explanations stay.
2. **`card-only` profile:** accepted. In the player shell (`bridge_harness/gen9.py`, `read_calls`) the reserved profile id is `card`: that row is the card's term alone, no scorer. For a net profile `k` the row is `S_k` plus the card's term on `k`'s residual contexts. So the reader's `type_log_score` takes one more keyword, `profile=None`: `None` is the full term (the `card` profile); a system id restricts it to that profile's residual contexts. I am changing the shell to pass it; please give `CardFactor` the keyword and a factory `bridge_harness.cards.factor:shell_reader(model, other, root)` that builds it from a `PlayerModel` (its `bidding` card, `Deviation` from the `bid.<family>` counts in `model.stat(...)`).
3. **Families and the experience record:** as you list them. `bid.<family>` is a `count` with `agree`, `deviate`; signed misses are `hist` statistics named `bid.miss.<rule>.<feature>`; the profile evidence is the `loglik` named `profile`. dave's store (merged, `experience_store.py`) takes them as they are.
4. **A caution on the mixture.** `S_k` is a classifier's log score, your `F` is a proper log-likelihood. Mixing them in one log-sum-exp compares numbers on different scales, so the posterior between `card` and a net profile is only as good as the scales happen to be. That is one reason for E9-8.

**E9-8, please run it before E9-1's played part** (I am writing the experiment file now; an hour of sandbox at most). Your table says the hand-fit scorer gives 2.18 nats on house auctions. The bidder is deterministic and its inputs are exactly the hand type (BEN's features are points, lengths, A K Q J T and the count of low cards per suit), so for any profile whose generator we hold, the exact reading of a seat's calls is a replay: does this hand type make these calls. That is what your `rb_meanings` does for the rule bidder, applied to the house nets with `system_bidders.BenLstmBidder`. Measure, with your harness, on house Gen 6 auctions (the arena's bidder) and Gen 5: scorer; replay with a small `eps`; replay with the bidder's own softmax as the likelihood; scorer as the proposal and replay as the correction on a pool of 512. If replay is worth a nat or more over the scorer, it becomes the reading for every profile with a known generator (house nets, BEN's own bidder, rule bidders, cards), the scorer becomes the proposal that draws the pool, and the mixture compares proper likelihoods. It would also be a gain against house bots, not only foreign ones.

**The two crashes in `rule_bidder.py`:** I am passing them to g8 on the board.

**Reviews from now on:** module PRs are reviewed by another lead (yours by sam, sam's by you), design notes and experiment verdicts by me. I was the queue for the last half hour.
