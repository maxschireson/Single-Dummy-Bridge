D6 wiring: ec2694d counts a floor deal twice for a guest (occasions name the opponent), against your 07:27 unit; identical bid evidence doubled. Pick A/B/C

will, 12 Nov 09:24 UTC. Task G9-D6.

From will, 12 Nov 09:25 UTC. Your call before you release D6.

G9-D7 is accepted (my review: inbox/dave/20261112T0924Z). One change dave made during the rehearsal reverses a rule you adopted, so I'm putting it to you.

**The rule.** At 07:27 you adopted (family, seats, auction) as the experience store's unit of repetition. In ec2694d, occasions also name the opponent, so the same deal, in the same seats, after the same auction, against `9a-32` and against `8p-32` (the floor pairs) counts twice.

**What the rehearsal shows.** The old rule merged these occasions for guest-a:
- 24 bid occasions, all with identical deltas against the two opponents: the same auction, so the same calls.
- 20 card occasions, 12 with different deltas.

**What it does to the run.** Floors are 600 of 1,200 boards in epochs 2 and 3, and 1,000 of 1,200 from epoch 4. Under the new rule, most of a guest's bid counts and its `profile` log-likelihood would be doubled copies of the same evidence. P(card) and the off-card rates would move about twice as fast as the data warrants.

**Options**
- A: bid occasions without the opponent, card occasions with it. Identical bid evidence counts once, and card play against different defenders counts as two observations. This is my suggestion.
- B: your 07:27 rule for both.
- C: keep ec2694d as it is.

Whichever you pick, it is a few lines in `board_envelopes` (dave's).
