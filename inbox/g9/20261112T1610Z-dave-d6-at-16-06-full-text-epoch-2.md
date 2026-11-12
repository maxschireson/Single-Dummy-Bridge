D6 at 16:06 (full text): epoch 2 under way; floor boards 45.6 CPU-s on azure4; end about 23:00 UTC

dave, 12 Nov 16:10 UTC. Task G9-D6.

From dave, 12 Nov 16:12 UTC. Task G9-D6. (My 16:10 message lost every name in backticks to the shell; this is the full text.)

- **Progress.** By 16:06 the run had 1,114 of 6,200 boards: all of epoch 1 (600) and 514 of epoch 2's 1,200. There are no item-6 errors and no restarts.
- **Events.** The registry has, in order before epoch 2: `activate 9a-32`, `open-test 9a-32` against `8p-32`, and `submit guest-a`. guest-a's first model is card 0.661, flat 0.165, house-dds40k 0.046, and the rest smaller.
- **Epoch 2's schedule.** Self-play `8p-32~8p-32` 10, and the promotion pair `9a-32~8p-32` 30. The gain pool's 60 units went to:
  - guest-a against each anchor, 14 each;
  - 7s-32 against each anchor, 12 each;
  - `7s-32~8p-32`, 6;
  - `8p-32~1`, 2.

  `guest-a~8p-32` got nothing because the floor `8p-32~guest-a` already measures it, and so did `8p-32~5RZ32`.
- **Cost.** In epoch 2, `8p-32~guest-a` floor boards cost 45.6 CPU-s each over 262 boards, not counting item 6. The same pair cost 34.7 over 24 boards in rehearsal 2. Other boards cost 15.9, as before. Overhead (item 6 and pool start-ups) is about 9% of the wall time.
- **Projected end: about 23:00 UTC.** That is 3,338 floor and 1,748 other boards left, at those costs. The queue says 23:27. Not known yet: what `9a-32`'s floor boards cost; it is the Gen 9 bot and has not started its floor.
