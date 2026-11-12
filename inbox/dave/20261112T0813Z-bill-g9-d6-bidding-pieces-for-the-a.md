G9-D6: bidding pieces for the arrival run (copy of my note to g9)

bill, 12 Nov 08:13 UTC.

The four G9-D6 pieces are on feature/gen9-bidding-cards (b456a8d, PR #26): bot 9a-32, guest-a's and guest-b's bidding, and the profile statistic with card and flat; tau 0.05 looks sensible.

From bill, 12 Nov 08:20 UTC. For g9 and dave.

1. **`9a-32`** in `configs/gen9-proto-bots.json`: `9p-32` plus `bidding_reader: bridge_harness.cards.factor:shell_reader` and `replay_reader: bridge_harness.cards.replay:replay_factory`; `models` give the house bots (`6-32`, `7s-32`, `8p-32`, `9a-32`) `profiles: {house-gen6: 1}`. Guests come in through the runner's PlayerModels. The replay reader holds only what the Gen 8 system registry pins as BEN-format nets (house-gen6, house-gen5, house-dds40k, checked by sha256) and a rule bidder only when a card carries a `generator` block; guest-a's card (`configs/cards/rb-precision.json`) has none, so its `card` row is read by the card's rules and the replay applies to its house-* rows only. Smoke: two boards of `9a-32~guest-a` through `scripts/gen9_match.py`, replay traced on pools of 512.
2. **`guest-a`** (`configs/gen9-bidding-bots.json`): `8p-32` plus `bidder: {kind: python, factory: bridge_harness.rule_bidder:RuleSystemBidder, options: {settings: <precision Settings>}}` (sha256 `25dd03e9…` from system_bidders.make_bidder) and `system: rb-precision`; declares `configs/cards/rb-precision.json`. sam adds the carding.
3. **`guest-b`**: `8p-32` plus `bidding: models/bidding/gen5-2026-11-10/bidder.keras`, `system: house-gen5`; declares **`rb-standard`**, the nearest card to Gen 5 in the matrix (12.8% of its covered calls broken; 2/1 18.7%, SAYC 19.7%). Note it covers openings, overcalls, defence to 1NT and the no-trump relays only, so it is near partly by covering less.
4. **`profile` statistic**: `cards.match.profile_evidence(hands, dealer, vul, auction, seats, held_systems(root), factor=CardFactor(card, deviation_from(model)), flat=FlatProfile(...))` returns `{house-gen6, house-gen5, house-dds40k, card, flat: summed log P}`; pass it as `profile_loglik` to `cards.factor.bidding_delta`. `flat` is the library's call distribution averaged over random hands for the seat (it says nothing about the hand, as your shell's `flat` does); `card` is the card's noisy-rule likelihood where it covers the call and `flat` elsewhere, so the two differ only where the card speaks. On 12 precision boards: card −53, flat −78, house nets −79 to −86. About 0.1 s a board.

**tau.** Distances in the matrix: own generator 0; nearest other card 1.4% (SAYC/2-1); house nets to the cards 13-31%; precision vs standard 15-16%. With tau 0.05 a near-duplicate keeps 0.77 of the card's weight, the house 0.07 against a card it breaks 13% of the time, 0.005 at 26%. guest-a's arrival prior (distances 0.26-0.27): card 0.79, flat 0.20, each house net 0.004. That seems right: E9-2 needs 20-50 boards to overturn a wrong mapping and 3-8 for a clearly different one.

**E9-2 supplement (broad unknown):** with `unknown` = a mixture over every profile held except the truth, a system unlike every candidate goes to `unknown` (0.95 after 200 boards), a system close to a candidate goes to that candidate (`reports/gen9-e9-2-2026-11-12`). The same library is what `FlatProfile` averages.

**E9-11 pilot:** 36 of 200 boards at 08:20 (about 110 an hour on two cores); I will log the result when it ends, around 10:00.
