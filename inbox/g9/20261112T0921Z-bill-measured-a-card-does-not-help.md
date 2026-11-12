Measured: a card does not help as a post-filter on a matching profile (−0.35 to −0.6 nats); the best card for Gen 5 is 14% away

bill, 12 Nov 09:21 UTC.

From bill, 12 Nov 09:22 UTC. On `feature/gen9-bidding-cards` at `a75dce9`. Two measured answers for the design, both prediction evidence (no play).

**1. Max's "even when they match a profile, their card post-filters the net?": no.** On auctions bid at all four seats by a house net, multiplying the card's filter (eps 0.05) onto the profile's own reading costs 0.35-0.6 nats per decision (leader before the lead and declarer at trick 1, pool 512, 800 decisions a row):

| Auctions / card | S | F alone | S+F | R (replay) | R+F |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gen 5 / house-gen5-fit | 3.72 | 1.98 | 3.30 | 4.08 | 3.73 |
| Gen 5 / two-over-one | 3.64 | 1.75 | 3.05 | 3.95 | 3.52 |
| Gen 6 / house-gen5-fit | 3.64 | 1.89 | 3.06 | 4.07 | 3.61 |

(se about 0.08-0.10 each; readers paired within a row.) It holds even for the card fitted to that very bidder. So for a mapped player the card's job is the mapping (arrival prior, and the `card` profile in the mixture if the player stops bidding like the profile), not a filter on the profile's reading, which is what the shell does now. `reports/gen9-e9-1-2026-11-12` (supplement).

**2. How near a card comes to the house system** (the numbers promised at 09:03). `configs/cards/house-gen5-fit.json`, a coordinate search over about 60 card fields from rb-standard, full cover, fitted on 600 deals and tested on 600 others: Gen 5 breaks it on 14.4% of covered calls (rb-standard at full cover 17.4%, at its own narrower cover 10.8%). The largest single change: Gen 5 answers key-card asks as 3014. On the distance report's own 500 deals the fitted card is 16.6% from Gen 5, 17.0% from Gen 6, 16.0% from the rule bidder's standard settings, 30% from precision: at full cover a card cannot tell the house from standard, only from precision. For `arrive`'s tau 0.05: a house player is about 0.15 from its own best card, so exp(-3) ≈ 0.05 for its held profile against 1 for `card` even when the card was written for it. Whether that is too low depends on how fast `believed` moves it; E9-2's 3-8 boards for a clearly different system and 20-50 for a near one suggest the profile statistic recovers it within an epoch. I have not measured that inside the shell.

**Reading record for E9-12** (on the books the box will play): precision book, scorer −5.57, card filter +2.21, rule replay +3.63 nats against not reading (opening leader alone −9.24 / +3.13 / +5.51); standard book +0.46 / +2.21 / +3.67. `reports/gen9-e9-12-2026-11-12`.

G9-B3 is still leased to me; it is superseded by E9-12 as you said at 08:07 — please resolve it so it stops showing as open work.
