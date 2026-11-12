# Card-to-profile distance (G9-B4, 12 November 2026)

**Prediction evidence.** Code: `scripts/gen9_profile_distance.py`, `bridge_harness/cards/match.py`
(`card_distance`) on `feature/gen9-bidding-cards`. Data: `result.json` (500 deals, the same
deals for every generator, all four seats bid by it).

Distance = percent of the calls a card covers where the card's first fitting rule is not the call the
generator made. `card:<id>` is that card's own bidder (covered contexts by its rules, the rest by the
rule bidder's standard settings). Rows are generators, columns are cards.

| Generator \ card | two-over-one | sayc | acol | precision | polish-club | rb-standard | rb-precision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rb-standard | 17.1 | 16.6 | 25.6 | 26.8 | 23.3 | 0.0 | 15.5 |
| rb-precision | 31.2 | 31.0 | 33.9 | 11.4 | 24.9 | 16.1 | 0.0 |
| house-gen5 | 18.7 | 19.7 | 29.4 | 30.2 | 25.4 | 12.8 | 26.3 |
| house-gen6 | 19.3 | 20.2 | 29.8 | 30.7 | 25.9 | 13.2 | 27.2 |
| card:two-over-one | 0.0 | 1.4 | 13.1 | 17.9 | 8.6 | 9.3 | 23.9 |
| card:sayc | 1.4 | 0.0 | 12.0 | 19.1 | 10.0 | 9.2 | 23.8 |
| card:acol | 13.0 | 12.0 | 0.0 | 21.5 | 18.4 | 21.8 | 26.5 |
| card:precision | 21.4 | 22.5 | 25.7 | 0.0 | 15.8 | 21.9 | 6.4 |
| card:polish-club | 14.3 | 15.3 | 22.9 | 17.0 | 0.0 | 19.8 | 21.3 |

- Every generator is at 0 from its own card. The two house nets are closest to the card written for
  the rule bidder's standard settings (13%) and break the 2/1 card on 19% of its covered calls; the
  house's own system is not well described by any card here, as expected for a net with no card.
- SAYC and 2/1 cards are 1.4% apart; Acol is 12-13% from both; Precision 18-23% from the natural cards.
- Residual of the house nets against `rb-standard` (families broken on more than 10% of at least 20
  calls): Gen 5 ['comp_jump', 'comp_overcall', 'comp_pass', 'nt_answer', 'open_minor', 'open_weak', 'resp_nt_relay']; Gen 6 ['comp_jump', 'comp_overcall', 'comp_pass', 'nt_answer', 'open_minor', 'resp_nt_relay']. These are the contexts where
  a player who declares that card but bids like the house profile would be read by the card's filter,
  and the profile's scorer elsewhere (design note section 3).
