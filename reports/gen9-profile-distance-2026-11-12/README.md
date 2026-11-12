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

## Supplement, 12 Nov 09:10 UTC: the best card for house Gen 5 in this language

`configs/cards/house-gen5-fit.json`, written by `scripts/gen9_fit_card.py`: a coordinate search over
about 60 card fields (two rounds, 21 changes kept), starting from `rb-standard` with its cover dropped
(the fitted card covers every context), minimising the rate at which Gen 5 breaks the card on covered
calls. Fitted on 600 deals (seed 6161), tested on 600 fresh deals (seed 6162):

| Card (cover) | Gen 5 breaks, fit deals | Gen 5 breaks, test deals | covered calls (test) |
| --- | ---: | ---: | ---: |
| rb-standard (its own: openings, overcalls, defence to 1NT, NT relays) | | 10.8% | 1,699 |
| rb-standard (every context) | 17.7% | 17.4% | 2,429 |
| house-gen5-fit (every context) | 12.9% | 14.4% | 2,430 |

The largest single change was `slam.blackwood: rkc3014` (12.9 from 13.7): Gen 5 answers key-card asks
as 3014. Families still broken on more than 10% of their calls on the test deals: adv_overcall,
ask_answer, comp_jump, comp_overcall, nt_relay2, open_weak, rebid_*, resp_comp, resp_new, resp_nt,
resp_nt_relay, resp_pass, resp_raise.

Its column on this report's 500 deals (seed 5150; `house-gen5-fit-column.json`):

| Generator | house-gen5-fit | rb-standard (own cover) |
| --- | ---: | ---: |
| rb-standard | 16.0 | 0.0 |
| rb-precision | 30.0 | 16.1 |
| house-gen5 | 16.6 | 12.8 |
| house-gen6 | 17.0 | 13.2 |

- The best card this language can write for the house system is still broken on about 15% of the calls
  it covers (14-17% by deal set; calls within a deal are correlated, so a deal set of 500-600 moves the
  rate by about 1.5 points). Every house player is that far from its own best card.
- At full cover the fitted card does not separate Gen 5 from the rule bidder's standard settings
  (16.6 against 16.0); it does separate both from precision (30). Distances measured at different covers
  are not comparable: a card that covers less looks nearer.
