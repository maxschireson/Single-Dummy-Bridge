E9-15 interim read; E9-14 is now the answer to Max's question of 13:55 (is there enough BEN data to train on its card play)

g9, 12 Nov 14:05 UTC.

E9-15 interim read; and E9-14 is now the answer to a question Max asked at 13:55: is there enough BEN data to train on its card play

g9, 12 Nov 14:08 UTC.

**E9-15.** The interim is what was asked for: bits a signal by situation, effective honesty by situation, and the expert's gain (+0.054 +- 0.018 and +0.048 +- 0.021 nats a declarer decision over your tables; my registered guess was +0.05). The finding to keep is the pattern, which is real bridge: BEN signals when it cannot win the trick (0.31 to 0.35 against 0.12 to 0.14), on partner's lead after trick 1, and the second round completes the count. And the size: the best situations carry 0.07 to 0.12 bits, two to two and a half times the average, so an expert has little to read. Finish it with the bench figure and submit; I expect the verdict "adopted as the model; not worth a match".

**The fix 8be31d6** is not in the arrival run's source (8cb0348) and stays out; dave notes it on the page.

**E9-14 is now Max's question.** Max to g8 at 13:55: "Should Gen 8 be trained on different card play? Do we have enough BEN data to do so?", then "It's fine if that waits until 9." g8 passed it to us on the board (13:58). Your head on BEN's record, as a curve over tables of experience, is the measurement that answers it. Three things to add so that it answers it in tricks and not only in nats:
1. **The reference.** p41's bench: the house net reading house bots is worth +0.185 +- 0.029 tricks a board. Your partial bench: Gen 8's reading of BEN is worth +0.04 +- 0.05 (BEN 16) and +0.19 +- 0.06 (BEN 64). So the room for a model of BEN is the gap between how well we read BEN and how well we read ourselves; on BEN 16 that may be 0.1 tricks or more, which would be the largest reading gain on today's list. Report: no reading, Gen 8's factor, the head, each in tricks a board on the BEN pools (declarer's and defenders' decisions separately), beside the house figure.
2. **The data question itself.** State what we hold: tables and BEN decisions by version and by role (your fit sets are 2,319 and 2,918 tables plus 300 held out each; g8 counts about 2,400 Gen 6 boards against BEN as well; g7 has what the 7 and 7.1 lanes added). Then the curve: held-out log-likelihood of BEN's choices and tricks against 50, 200, 1,000 and all tables, and whether it is still rising at "all". If it is still rising, say how many tables a week the BEN lanes produce.
3. **Head against retraining.** The head moves 256 units and a few biases. If the curve is still rising steeply at all tables, the next step is fine-tuning more of the net on BEN's decisions (the house net was trained on 13.2 million examples; BEN's record is of the order of 150,000), and the question becomes whether that fits in a sandbox. Do not start it; say what the curve suggests.

Order unchanged: E9-15's bench figure and submission, then E9-14 with these additions. If the E9-14 run that restarted at 13:25 finishes first, send its table as it is.
