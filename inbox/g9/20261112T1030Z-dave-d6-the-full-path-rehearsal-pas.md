D6: the full-path rehearsal passed (guest-b, retirement, replay); four choices before the release

dave, 12 Nov 10:30 UTC. Task G9-D6.

From dave, 12 Nov 10:35 UTC. Task G9-D6.

**The full-path rehearsal passed.** Records are on `transfer/gen9-arrival-rehearsal-full-20261112` (8d9aa04); the page is `report.md`. It ran the box run's events file on five 16-board epochs, with floors of 4 (guest-a) and 3 (guest-b) boards a pair. It ran in a fresh worktree of 4354b64, where only the on-first-use code restored the nets. The run took 19 minutes, 31 CPU-minutes.

**Checks that passed:**
- guest-b's submission computes its first model with `arrive`: card 0.692, flat 0.173, house-gen5 0.054, house-gen6 0.049, house-dds40k 0.032.
- The queued command retires 7s-32 before epoch 4, and guest-b's floor starts at epoch 4.
- In every epoch, the snapshot equals the merge of the earlier epochs' envelopes.
- The epoch-3 floor board replays with the same trace and the same manifest identity.
- The new pieces (guest-b's corrected bidding hash, the plan-event fields) are in source after 4354b64 and covered by tests. They were not in this run.

**What the bots read.** These are 16-board epochs, so the numbers show the wiring, not the effects.
- guest-a: P(card) 0.984 from epoch 3, which is the floor's ceiling. Honesty 0.62 after 5 boards, 0.68 after 17.
- guest-b, after 3 boards and then 6: P(card) 0.004. The mass is on house-gen5 0.38, house-gen6 0.38, house-dds40k 0.23, so Gen 5 is not yet told apart from Gen 6 (bill expects 10 to 20 boards). Honesty is 0.24, from a prior of 0.5.

**Box time.** Here a board costs 23 CPU-seconds. At 8 workers, 5,400 boards would take about 4.4 hours, if azure4's cores match this machine's and the board mix matches. I have not measured either.

**Two scheduling facts for the floor-share question (both rules v0, accepted in D4):**
1. **Self-play takes most of the scheduled boards.** Of the boards the scheduler places, 75% are the champion's self-play: the training share (.55) plus the promotion share (.20), which goes to training while no test is open. The two panel pairs get 8% each and each admission pair 1%. In epochs 4 and 5, about 150 of the 200 scheduled boards would be `8p-32` self-play.
2. **The betting test may not open.** It opens only once 9a-32 is admitted (se ≤ 0.15 or 2,000 boards) and rated above the champion. I do not know whether that happens within five epochs, because most of its boards are floors against a candidate. In the rehearsal it had 0 direct boards. If you want item 4 to show a live test, the events file can say `activate 9a-32` and `open-test 9a-32` (champion `8p-32`) before epoch 2. That works now (65d77ec, with a test) and puts `9a-32~8p-32` in the promotion share: about 120 boards an epoch in epochs 2 and 3, 40 in epochs 4 and 5. That is not enough for the test to decide at d = 0.1, but it would show its state.

**Waiting on you:**
- the card occasion setting (`auction`, `opponent` or `play`; sam's 10:10 note favours `play`);
- floors as they are, or 1,600-board epochs from epoch 4;
- whether to open 9a-32's test by plan;
- the release.

The job file is ready at source 65d77ec. Will notes D6 ties with E9-0 at priority 1, so E9-0 must be submitted first to run first.
