D6 done: the page is on transfer/gen9-arrival-20261112; item 1 +0.48 (0.13) IMPs against guest-a; guest-b's native result below its band

dave, 13 Nov 00:57 UTC. Task G9-D6.

From dave, 13 Nov 01:05 UTC. Task G9-D6.

**The arrival run is done:** 6,200 boards, no failed boards after the resume, no item-6 errors. The page is `report.md` on `transfer/gen9-arrival-20261112` (c9cb575), with the registry log, epoch manifests, records and snapshots.

**Against the registered predictions:**

| Item | Result | Prediction | |
| --- | --- | --- | --- |
| 1. 9a-32 minus 8p-32 against guest-a, native, pooled over 1,200 deals | +0.479 (0.131) IMPs; epochs 2 to 5: +0.43, +0.48, +0.53, +0.47 | +0.2 or more | met |
| 2. guest-a's P(card) | 0.984 from epoch 3 (the floor's ceiling) | above 0.95 | met |
| 2. guest-a's honesty | 0.776, 0.766, 0.761 in epochs 3 to 5 | 0.65 to 0.8 | met |
| 2. guest-b's honesty | 0.024 at epoch 5 | below 0.25 | met |
| 2. Item 1's rise from epoch 2 to epochs 3 to 5 | about +0.06 | less than its SE (0.26) | as predicted |
| 3. guest-b, native | epoch 4 -0.060 (0.240); epoch 5 -0.360 (0.232); pooled -0.210 (0.167) | each epoch within ±0.2, pooled within one SE of zero | epoch 4 met; epoch 5 and the pooled figure not |
| 6. Reading, guest-a | +4.44 (0.19) nats | above 8p-32 | met |
| 6. Reading, guest-b | -0.147 in epoch 4, -0.004 in epoch 5 | not more than 0.3 below | met |

Play factor chosen (item 2): **not produced.** The pipeline writes no `play.info` statistic, so the column is empty; the page says so.

**4. The arena:**
- guest-a was admitted at epoch 4 on boards (2,174 boards; se 0.22 against the target 0.15). guest-b stays a candidate.
- Ratings at the close of epoch 5: 9a-32 +2.23, guest-b +2.14, 8p-32 +2.07, 7s-32 (retired) +2.06, guest-a +1.03, 5RZ32 +0.74, each about ±0.4.
- 9a-32's betting test against 8p-32: 669 direct boards, K 1.17, L 0.70, no decision, as expected.

**5. Replay.** The replayed board was played under 8cb0348 and replayed at 698679e. It is identical card for card, and so is its manifest identity.

**Two things from the records that the items do not show:**
- **Against guest-a, native minus common is -0.054 (0.153).** That is the per-deal difference between the native and common regimes in 9a-32 minus 8p-32. The common regime's +0.533 (0.104) comes from reading guest-a's cards; the auction is read as a house auction there. So this run shows no sign that reading the auction added IMPs beyond what reading the cards gave, despite item 6's +4.4 nats. That fits bill's finding that auction nats at the lead are worth little at the table.
- **Against guest-b, native minus common is -0.347 (0.160),** and -0.493 (0.219) in epoch 5. Common alone is +0.137 (0.150). Item 6 says the auction reading at the first decision after the lead is level in epoch 5, so the cost is somewhere else at the native tables. I have not found where. Candidates I would check first:
  - the opening lead, where the lead net reads only house auctions;
  - the reading at later decisions.

  It could also be noise: it is 2.2 SE, and one of several comparisons.

**E9-17** is submitted for a verdict (feature/gen9-e9-17, 8caedc7). Rule reader minus scaled net: t-high -0.098 (0.142), t-low +0.085 (0.141), t-random -0.142 (0.140); pooled over t-high and t-low, -0.006 (0.100). The prediction is not shown, and I suggest the verdict inconclusive.
