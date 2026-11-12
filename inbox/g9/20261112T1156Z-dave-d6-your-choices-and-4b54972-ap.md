D6: your choices and 4b54972 applied (7175ae7); item 6 and the release check on the page; rehearsal running

dave, 12 Nov 11:56 UTC. Task G9-D6.

From dave, 12 Nov 11:58 UTC. Task G9-D6.

Your 11:32 choices and 4b54972 are in `feature/gen9-arena-arrival` at 7175ae7. The full suite passes (440, 0 failed).

- **Rules** (`rules-arrival.json`, version arrival-v2):
  - epochs of 600, 1,200, 1,200, 1,600 and 1,600 boards;
  - floors of 300 boards a pair, guest-b's included;
  - occasions: bids by auction, cards by play;
  - shares: self-play 0.10, promotion 0.30, gain 0.60 over admission and panel pairs.
- **The gain rule.** I wrote it into the scheduler (`arena9.gain_units`), because rules v0 had fixed shares. It gives one chunk at a time to the pair whose next chunk most cuts the total variance of the centred ratings, the same variance schedule as in E9-5's simulator. It starts from the last close's ratings and takes in the epoch's floors and promotion boards first. A purpose with no pairs gives its share to the pool, not to self-play. The ×2 weight cap does not apply to the pool. Epoch 1 has no ratings yet, so its pool is split evenly.
- **Events:** `activate 9a-32` and `open-test 9a-32` against `8p-32` before epoch 2.
- **Item 6** (`arena9_pipeline.reading_gain`), measured after each floor board:
  - At each native table, take the first decision of the bot's side after the opening lead.
  - Score the auction's log weight on the true layout, as that bot reads it, minus the log of its mean over every layout consistent with what it sees.
  - The mean is exact over hand-type classes, with the class weighting your 379273e uses.
  - For each floor pair, the bot is a fresh instance from the pair manifest, with `meet(guest)` and `auction_by(None)`. A failure is written into the row and does not stop the run.
- **The page:**
  - item 6 by guest and epoch, with the paired difference by deal;
  - your release check, evaluated;
  - the predictions from the revised task (now in `arrival-events.json`) beside items 1, 2, 3 and 6;
  - the run's shares.

A check on one recorded board with the rehearsal's epoch-3 models confirms that 9a-32's item-6 numbers come out different from 8p-32's. Without the models handed over, 9a-32's equal 8p-32's, as they should.

**Second full-path rehearsal: running now** in a fresh worktree of 7175ae7. Epochs are 16, 24, 24, 40 and 40 boards; floors are 6 boards a pair for guest-a and 10 for guest-b, so the guest-b check after its first epoch rests on 10 deals. I will send the page in about 35 minutes. If the check is met I will submit; if not, I will send you the page.
