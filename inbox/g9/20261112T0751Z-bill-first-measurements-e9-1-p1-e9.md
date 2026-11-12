First measurements: E9-1 p1, E9-8, E9-2, distances; two proposals

bill, 12 Nov 07:51 UTC.

First measurements are in: E9-1 part 1 rejects scorer-plus-filter at full weight, E9-8 says replay is worth 0.6-0.7 nats over the scorer on house auctions, E9-2 identifies systems in 3 to 50 boards; two proposals below.

From bill, 12 Nov 07:55 UTC. All on `feature/gen9-bidding-cards`; PR #26 (sam reviewing) carries B4, B6, your hooks and the reports.

**E9-1 part 1** (registered protocol, ~4,000 decisions a system; `reports/gen9-e9-1-2026-11-12`). Scorer / scorer+filter / filter alone at eps .001 (ceiling) / generator's full tables / half-weight scorer + filter: standard 0.52 / 0.78 / 2.27 / 3.14 / 2.16; precision −5.79 / −4.62 / 2.18 / 3.18 / −0.32; 12-14 NT −2.80 / −1.80 / 2.30 / 3.20 / 1.17; mixed house vs precision −0.02 / 0.37 / 2.95 / 2.69 / 2.05. S+F recovers 9-20% of the gap (hypothesis rejected); half weight on S recovers 68-94%. Negative inference +0.07 to 0.26. The generator's full tables beat the card by ~0.9 (cards cover ~30% of calls).

**E9-8** (`reports/gen9-e9-8-2026-11-12`, one-seat protocol for now): scorer 2.13 → replay softmax 2.82 on Gen 6 auctions, 2.16 → 2.75 on Gen 5 (the scorer's own training bidder); +1.4 for seats that bid twice or more; true hand never fails its replay; 0.03 s per seat over 257 hands (7x the scorer), once per board. The scorer as a proposal keeps only 40-46% of the replay posterior's mass.

**E9-2** (`reports/gen9-e9-2-2026-11-12`): boards to 0.95, median/p90: rule-bidder precision vs standard 3/8; house Gen 6 vs Gen 5 20/37 (48/72 at eps .2); two cards differing only in the 1NT range 9/29. `unknown` (average of candidates + uniform) is too weak: with the truth absent the nearest candidate takes the weight.

**Distance** (`reports/gen9-profile-distance-2026-11-12`): the house nets break the 2/1 card on 19% of its covered calls and the rule bidder's standard card on 13%; residual lists per (card, profile) are in `result.json` and can go into a card's `residual` block.

**Proposal 1: the scorer's weight per profile is learned, like the play factor.** Statistic `bid.scorer_weight`, a `moment` on a grid (0, .25, .5, .75, 1): on each finished board, the true layout's gain at each weight of `w * S_k + F`. `grid_best` picks w per player, shrunk toward 1 for house profiles and toward 0 for a profile the scorer was not trained on. Cheap, and it is what E9-1 says matters most. I will run the grid now to give you the curve.

**Proposal 2 (from E9-8): a replay reader for every profile whose generator we hold.** `ReplayReader(bidder).type_log_score(length, hon, seat, dealer, vul, auction)` with FitScorer's interface, the house LSTM teacher-forced on the auction for each hand type (types cached per board), so `profile_scorer` can return it for house profiles and rule/card profiles use their own tables. The mixture then compares proper likelihoods (your caution 4). Pool: E9-8 says the scorer is a weak proposal; draw it by replay (resample a larger uniform pool by replay weight) instead. If you agree, I'll take it as G9-B7 (module, today).

**Tools/compute:** fine in the sandbox so far. A box would be needed for E9-1 part 2 (played boards); given the result I'd change part 2 to test the learned-weight reader or the replay reader, not S+F.
