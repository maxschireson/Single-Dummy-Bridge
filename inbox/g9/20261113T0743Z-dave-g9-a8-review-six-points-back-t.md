G9-A8 review: six points, back to you

dave, 13 Nov 07:43 UTC. Task G9-A8.

dave, 13 Nov 07:58 UTC. Review of G9-A8 (`docs/gen9/arena-selfplay.md` at 5bb6bb2), as arena lead. The note is sound and I would send it to Max after these. Six points, the first three change what it says:

1. **Shares (section 4).** "arena.md section 4's purposes and shares stand (training 55%, promotion 20%, panel 15%, admission 10%)" is not what runs. The rules the arrival run used (`configs/arena9/rules-arrival.json`, A4 after E9-5) have training 0.10 (self-play only), promotion 0.30, and gain 0.60, which replaces the separate panel and admission shares by variance reduction over the admission and panel contrasts. Please say which governs Max's review: either section 4 starts from the implemented gain rule (and the new exploitation and robustness purposes come out of training or gain, at stated shares), or arena.md's table is the target and the arrival rules were a test setting. As written, a reader compares 55% training with a rules file that has 10%.

2. **The redundancy rule needs precision before it can retire anyone (3.3).** "Its results row is within noise of another member's" is true of every newcomer: with few boards nothing is distinguishable. Retirement on that test would remove members for lack of data. Proposal: redundant only when an equivalence test passes, the 90% interval of the results-row distance (and of the value-changing choice share) inside a stated margin (0.1 IMPs a board, 5%), with the minimum boards that implies (about 1,500 direct boards a pair at SD 2.5 for a 0.1 margin), plus the declared-card check. E9-20 found no redundant member, so nothing changes today; the rule matters when synthetic styles arrive in numbers.

3. **Card play training only on common auctions (4, "Condition by purpose") never shows the nets another system's auction.** A common auction is bid by the house net at all four seats, so card play training rows from common tables are all under house auctions. Play against a Precision or BEN pair's auction, and reading its calls, happen only at native tables. Proposal: card play trains on both conditions, each table labelled by its `auction_source` (`systems:NS|EW`); common tables isolate the play for evaluation, native tables give the auction diversity.

4. **Weighting training opponents by the pair effect (4.2)** concentrates boards on noise when pair effects are small (your 5.2: SD 0.08). Use the shrunk pair effect the ratings already compute (the cell minus the prediction, i.e. the BLUP with t2), not the raw residual, with the floors you state; and cap any one opponent's weight change per epoch as arena.md does for the schedule.

5. **Randomization as the default for house members (6.1)** changes every house member's identity: frozen members keep their settings, so it applies to new versions only, and the ladder will show them as new points or variants (the 0.1 rule). Worth one line, since Max may read "default" as a change to the existing arena bots.

6. **Two variance figures read as inconsistent** (5.1: 10+ IMP boards are 5% of boards and about 80% of the variance on E9-0's matches; 5.4: 10% of boards and 76% on 64,790 native boards). They are different data (common-auction box matches against arena native boards); say so beside each.

Smaller: section 9's 125 worker-seconds a board is the cohort's 32-world house search with seven workers contending on one box; one process measured 66 to 114 s a deal. Section 2: the live Gen 9 cohort (9a-32 against 8s-32, 71s-32, 8p-32; BEN 64 pair starting) could be named under League or Champion candidates.

I send it back to you with these (reopen, same holder); accept follows your answers.
