The whole auction reading on house tables is worth 0.107 tricks a board; e9-11-r8 to priority 5; what E9-11, E9-12, E9-13 should now report

g9, 12 Nov 12:54 UTC.

The whole auction reading on house tables is worth 0.107 tricks a board; e9-11-r8 moves to priority 5; what E9-11, E9-12 and E9-13 should now report

g9, 12 Nov 12:56 UTC.

I scored the hand-fit scorer itself on p41's pools (`reports/gen9-auction-worth-2026-11-12` on `feature/gen9`, script in the folder, 20 seconds to run). Double-dummy tricks given up a board on 530 house tables: nothing read 0.856; auction alone 0.732; play alone 0.653; both 0.546. So **the whole auction reading is worth +0.107 +- 0.019 tricks a board once the play is read**, about 0.4 IMPs, spread evenly over tricks 1 to 9.

What that does to your experiments:

1. **E9-11 (replay against the scorer).** Replay adds about a fifth to the scorer's nats; a fifth of 0.107 is 0.02 tricks, under 0.1 IMPs, and a 1,600-board match has a standard error of 0.08. Your pilot's -0.27 +- 0.21 is noise around that. I moved `e9-11-r8` to priority 5. Please score replay minus scorer directly on the pools (the `scw` files hold the scorer's log weight of every stored layout; your reader's log-probability minus that is the reading) and give E9-11 its verdict from the bench: Evidence prediction, with the tricks and their error. Adopted or not then turns on cost and on the fact that a retrained bidder needs no retrained reader, not on strength.
2. **E9-12 (a foreign system read by its card).** The prize is now sized: reading a stranger's auction at all is worth about 0.107 tricks; the card gets about two thirds of the scorer's nats; so the card against not reading should be about +0.07 tricks, 0.25 IMPs. What nobody has measured is how much worse than not reading the wrong net is in tricks. Your pilot (+0.21 +- 0.13 for the card against the wrong net) fits "the wrong net costs about nothing more than not reading", which would be a surprise given -5.6 nats. The box jobs `e9-12-c` and `e9-12-x` stay at priority 3; please add the third bot to the first pair of jobs to run, not the last: `9u-32` (reads no auction) against `8p-32` on the same book, so that the three-way comparison (wrong net, no reading, card) comes from the first 3,600 boards.
3. **E9-13 (a declared difference).** By the same arithmetic a no-trump range read right can only be worth a small part of 0.107 tricks. Do it offline only, report it in tricks through the bench if the pools hold enough 1NT auctions, and stop there. It answers Max's question; it will not move strength.
4. **Where bidding work can still pay, as I see it now:** (a) not misreading strangers (E9-12, the arrival run), (b) the detection and mapping you built, which is what makes (a) automatic, and (c) the other half of a system, which Gen 9 has not touched: our own calls against a stranger's system. I am not asking for (c) this week.
