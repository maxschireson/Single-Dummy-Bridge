D6 at 16:06: epoch 2 under way; floor boards cost 45.6 CPU-s on azure4, so the end moves to about 23:00 UTC

dave, 12 Nov 16:10 UTC. Task G9-D6.

From dave, 12 Nov 16:12 UTC. Task G9-D6.

- **Progress.** By 16:06 the run had 1,114 of 6,200 boards: all of epoch 1 (600) and 514 of epoch 2's 1,200. There are no item-6 errors and no restarts.
- **Events.** The registry has, in order before epoch 2: ,  against , and . guest-a's first model is card 0.661, flat 0.165, house-dds40k 0.046, and the rest smaller.
- **Epoch 2's schedule.** Self-play 10, and the promotion pair  30. The gain pool's 60 units went to:
  - guest-a against each anchor, 14 each;
  - 7s-32 against each anchor, 12 each;
  - , 6;
  - , 2.

   got nothing because its floor already measures it, and so did .
- **Cost.** In epoch 2,  floor boards cost 45.6 CPU-s each over 262 boards, not counting item 6. The same pair cost 34.7 over 24 boards in rehearsal 2. Other boards cost 15.9, as before. Overhead (item 6 and pool start-ups) is about 9% of the wall time.
- **Projected end: about 23:00 UTC.** That is 3,338 floor and 1,748 other boards left, at those costs. The queue says 23:27. Not known yet: what 's floor boards cost; it is the Gen 9 bot and has not started its floor.
