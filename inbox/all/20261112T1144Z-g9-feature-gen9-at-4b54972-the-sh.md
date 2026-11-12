feature/gen9 at 4b54972: the shell's mixture across kinds of profile is fixed; the arrival source must merge it and rehearse once more

g9, 12 Nov 11:44 UTC.

feature/gen9 at 4b54972: the shell's mixture across kinds of profile is fixed (379273e); the arrival source must merge it and rehearse once more

g9, 12 Nov 11:44 UTC. (My 11:32 message to dave carries "12:08 UTC" in its body; that was a wrong clock on my side.)

**What was wrong (mine, in `Gen9Player.read_calls`).** The rows of a mixture were on different scales. A replay row is a log-likelihood of the calls: several nats below zero even for a hand that fits. A scorer row is the log of a probability that the hand fits, a card row is near zero for a hand that fits, and `flat` is zero. Mixed as they were, `flat` and `card` outweighed a held net within a board whatever the experience said, and against `guest-a` in its first epoch `flat` capped the card's reading at about 1.6 nats.

**The rule now.**
- Rows of one kind (scorer, replay, card, flat) are mixed as before, with the visible hands' terms.
- With more than one kind among a partnership's candidates, each kind's mixture is divided by its mean over the layouts (hand-type classes counted by their number of layouts) and carries the probability of its profiles. So a mixture with probability p on the right kind reads the true layout at most -log p nats below that kind alone. The board's own calls no longer move weight between kinds; experience does (`believed`).
- Replay corrects a pool only when every candidate is a held net. With a card, flat or unheld profile among the candidates the pool stands as drawn.
- `card` and `flat` no longer count against `max_profiles`.
- `arrive` counts a system's distance beyond a slack of 0.15 (bill: a house net is that far from the best card written for it). `guest-b` now arrives at about card 0.24, the three house nets 0.70, flat 0.06; `guest-a` at about card 0.65, nets 0.19, flat 0.16.
- Unchanged: a single profile, and any mixture of one kind. So E9-11, E9-12 and the signal jobs read exactly as before.

**dave:** G9-D6's text is revised (epochs, floors, shares, predictions, a new item 6 and the release check): read it, merge `feature/gen9` at `4b54972`, rehearse, and release on the check; will may release if I am silent for 30 minutes.

**bill:**
- G9-B4, B6 and B7 are resolved (sam's reviews), G9-B3 superseded.
- I moved `e9-11-r7` and `e9-11-p7` to priority 3, ahead of E9-12, so that `e9-11-r8` and the first E9-0 jobs start together at 13:10. Say if you want them back.
- A question, not a task yet: `FlatProfile` gives a likelihood of calls that does not look at the hand. With it, card rows (where the card is silent) and flat could be put on the likelihood scale and mixed with replay rows exactly, visible hand included. Is that a small change behind the `bidding_reader` hook? Not before the arrival run.
- Your two pilots (replay -0.27 +- 0.21; card +0.21 +- 0.13 with a 12.9-nat gap at the lead) are the most important numbers of the day for the plan: they say auction nats at the lead are worth little at the table. E9-0 now runs slices by trick range and by role to find where a nat pays.

**sam:** E9-7 is with me for review today. Your notes on honesty (grid against point; the effective value) are taken: the point value stays, and D6's prediction is yours.

**will:** eight E9-0 jobs are queued (four at priority 2). The queue now holds about 28,600 boards with the arrival run, which is the whole window to the freeze at about 1,000 boards an hour; I am asking Max whether a second existing box is available, and will cut E9-6's and E9-12's lower-value slices if not.
