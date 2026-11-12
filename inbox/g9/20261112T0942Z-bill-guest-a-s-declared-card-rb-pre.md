guest-a's declared card (rb-precision) now covers responses: +0.25 nats for the card read alone; E9-12 resubmitted at ea550d3

bill, 12 Nov 09:42 UTC. Task G9-D6.

From bill, 12 Nov 09:42 UTC; copies to dave and sam (G9-D6).

card_from_settings, configs/cards/rb-precision.json and rb-standard.json now cover responder's first call to a suit opening (feature/gen9-bidding-cards ea550d3). Measured on E9-12's books, same pools, paired: the card filter alone +0.25 ± 0.02 nats a decision on precision (2.21 → 2.46), +0.26 ± 0.03 on standard; the opening leader 3.13 → 3.60. The bidder breaks about 2% of the responses it now covers (raises by support points), so the card is no longer exact on its own bidder; respond=False gives the old card and the tests check both. Covering rebids too did not help.

What it changes: guest-a declares the new rb-precision (by id, so D6 picks it up from the file), and guest-b's rb-standard covers more, so its arrival distances to the house nets will be computed over more calls. E9-12's jobs now play the new cards (resubmitted with --replace at ea550d3); E9-11's jobs stay at d4515bd (no card involved). The replay is still 1.2 nats ahead of the card on these auctions.
