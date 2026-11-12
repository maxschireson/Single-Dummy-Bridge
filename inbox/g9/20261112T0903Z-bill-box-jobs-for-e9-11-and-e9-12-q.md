Box jobs for E9-11 and E9-12 queued (source d4515bd); a restore fix every replay job needs; E9-11 pilot −0.27 ± 0.21 over 200

bill, 12 Nov 09:03 UTC. Task E9-11.

From bill, 12 Nov 09:05 UTC. For g9; copies to dave (D6) and will (queue).

**Box jobs queued** on azure4 (`workq.py jobs`), source `feature/gen9-bidding-cards` at `d4515bd`, 4 cores each:
- E9-11, priority 2: `e9-11-r8` 9r-32~8p-32 1,600 boards; `e9-11-r7` 9r-32~7s-32 and `e9-11-p7` 8p-32~7s-32, 800 each on the same deals (seed 9112). I cut the 7s-32 slices to 800 to leave room for E9-12 and D6.
- E9-12, priority 3: `e9-12-c` 9c-32 and `e9-12-x` 9x-32 against 8p-32 (1,200, precision book); then `e9-12-u` (9u-32, 600) and the standard-settings slice `e9-12-cs`, `-xs`, `-us` (600 each). The books are committed, so the auctions do not depend on the box's rule_bidder.py.
- Rough time, from the sandbox's 17-27 cpu s a board: E9-11 3,200 boards at 4 cores ≈ 4-6 h; E9-12 5,400 boards ≈ 7-9 h at 4 cores. Box cores may differ from the sandbox's; the queue's boards/hour will tell.

**A fix every box job with a replay reader needs (`d4515bd`).** The registry points house-gen6 and house-gen5 at `models/bidding/*/bidder.keras`, which git keeps only as parts. In a fresh checkout `ProfileReplay` found no file and refused the profile, so 9r-32 would have played as 8p-32 (and 9a-32 in D6 would replay only what a guest's `bidding` path happened to restore). It now runs the generator's restore script once under a lock. Checked in a fresh worktree: DDS built, one board of 9r-32~8p-32, 120 replay calls of house-gen6. **dave: D6's source needs `d4515bd` or a merge of it.**

**E9-11 sandbox pilot** (not part of the result; 200 boards, seed 9111, eps 0): 9r-32 v 8p-32 −0.27 ± 0.21 IMPs/board (won 21, lost 28). Cost +3% in search seconds; effective layouts per pool decision 208 against 279 (the replay sharpens the weights, no collapse). Correction to my 08:13 message: the pilot ran at about 200 boards an hour, not 110; it started at 08:01 and ended 09:01.

**Since 08:13**, on the branch: sam's four B7 notes (replay floor eps 0.02 by default, measured: it costs 0.15 nats a seat reading, about a fifth of the replay's gain over the scorer; refusals recorded; a guest's generator block is never replayed; guests play their carding packages); 9cs-32 and 9xs-32; the situation fields for the three real cards. sam accepted B7 by message (08:17) but it is still `submitted` in workq, and D6 lists it as a dependency.

**A note on tau, from fitting a card to house Gen 5** (`scripts/gen9_fit_card.py`, coordinate search over 60 card fields): the best card I can write for Gen 5 in our language still breaks about 15% of its covered calls on fresh deals (rb-standard 17% at full cover, 11% at its own narrower cover). So a house player is about 0.15 from its own best card, and distances measured at different covers are not comparable: a card that covers less looks nearer. With tau 0.05 the arrival prior puts a held profile at exp(-3) ≈ 0.05 even when the card was written for it. Numbers to follow with the card when the fit ends.
