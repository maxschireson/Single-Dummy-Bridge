E9-24 resolved (inconclusive): Floors' calibration by weight source: scorer, 8X, Gen 9

will, 13 Nov 09:21 UTC. Task E9-24.

Verdict by will (reviewer): inconclusive on the registered predictions, with a recommendation to act on the post-hoc result. Reproduced from the report's rows (feature/gen9 33ddcbe) with e924_report.py and the report's own outright-claim filter. Every figure in the Result matches:
- floor minus realised above 0.25: house +0.060 / +0.049, Precision scorer +0.099 / +0.107, Gen 9 +0.083 / +0.089;
- paired coverage -0.004, +0.009 and -0.022;
- true layout under 1% of uniform: scorer 108 of 667 (8 cards) and 86 of 563 (7), Gen 9 none;
- committed at a floor of 0.9 or more: scorer 231 lines covered 0.913, Gen 9 228 covered 0.965, house 180 covered 0.950; both commit in 206 and cover 200; scorer alone 25 covered 11; Gen 9 alone 22 covered 20.
As registered: (1) is in the predicted direction but not shown (Precision minus house is about 0.04 +- 0.035 at 8 cards); (2) is not met (a sixth less, not half); (3) is met by construction.
What supports adopting Gen 9's weights for conditional claims is the committed-line comparison, which was not a registered prediction. Its discordant failures are 14 (scorer alone) against 2 (Gen 9 alone): exact McNemar p 0.004. With the 1% result, the mechanism (the scorer misreads Precision auctions) is plain.
Recommendation: use Gen 9's weights in conditional claims as a design decision, and register the 0.9-threshold failure rate against a non-house system as the prediction for the next sample (another opponent system or other feeds), so that the claim rests on a registered test. 8X's read_layouts weighting was not run.
