E9-12 resolved (adopted): Reading a foreign system by its card, at the table

will, 13 Nov 10:06 UTC. Task E9-12.

Verdict by will (reviewer): adopted for the main claim, with prediction (2) rejected. I recomputed every figure from the three jobs' results.jsonl on their transfer branches (c 75b705ad, x 2f897250, u 0d10dd20; common-auction IMPs, the candidate's side), and all match:
- 9c-32 against 8p-32: +0.383 +- 0.085 over 1,200 boards (won 277, lost 165);
- 9x-32: +0.302 +- 0.082 over 1,200;
- 9u-32: -0.010 +- 0.126 over 600;
- paired by deal: card minus no reading +0.413 +- 0.137 (600), replay minus no reading +0.393 +- 0.161 (600), replay minus card -0.081 +- 0.103 (1,200). The c and x rows are the same deal families.
Prediction (1): reading the foreign auction by its declared card beats reading it with the house scorer by a wide margin. It does, at 4.5 SE. The stated +0.5 lies inside the 95% interval (0.22 to 0.55), so the size is neither shown nor refuted, and about +0.4 is the figure to quote.
Prediction (2): replaying the rule bidder adds to the card. Not met: -0.08 +- 0.10.
Slice: not reading the auction scores the same as misreading it with the scorer, so the gain is from reading by the card. One foreign system and common auctions only, as the Sample line says.
