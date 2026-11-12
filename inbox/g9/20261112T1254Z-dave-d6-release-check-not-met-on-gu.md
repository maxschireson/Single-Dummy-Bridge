D6: release check not met on guest-b (-0.43 nats with the snapshot); the gap is the card's term on the held nets; not submitted

dave, 12 Nov 12:54 UTC. Task G9-D6.

From dave, 12 Nov 12:56 UTC. Task G9-D6.

**The release check is not met on guest-b, so I have not submitted.** Records are on `transfer/gen9-arrival-rehearsal-2-20261112` (c9fc2c7): the rehearsal, its page, and the bid-only check rows.

**Rehearsal 2** ran in a fresh worktree of 7175ae7, with the box run's events and rules on epochs of 16, 24, 24, 40 and 40 boards, and floors of 6 (guest-a) and 10 (guest-b).
- **The wiring works.** All of these checks passed:
  - the arrivals came in at the new prior: guest-a card 0.66; guest-b card 0.24, nets 0.70, flat 0.06;
  - 9a-32 was activated and its test opened by plan;
  - the retirement and the floors happened as planned;
  - snapshots equal the earlier envelopes in every epoch;
  - the replay was identical.
- **Item 2 so far.** guest-a: P(card) 0.984 from epoch 3; honesty 0.76, 0.74, 0.75 against the prediction of 0.65 to 0.8. guest-b at epoch 5: P(card) 0.004, house-gen5 0.53, house-dds40k 0.46; honesty 0.23 against the prediction of below 0.25.
- **Item 6 on the page:**
  - guest-a: +4.71 (1.32) nats over 24 deals.
  - guest-b: -0.71 (0.30) in epoch 4 and -1.13 (0.46) in epoch 5, 10 deals each. Not met.

**Your bid-only check** (`scripts/arena9_reading_check.py`; partial at 12:53, still running):

| Guest | Model | 9a-32 minus 8p-32 (SE), deals | Threshold | Met? |
| --- | --- | --- | --- | --- |
| guest-a | arrival | +4.86 (0.87), 65 | > +3 | yes |
| guest-a | snapshot (epoch 5) | +4.89 (0.88), 65 | > +3 | yes |
| guest-b | arrival | -0.48 (0.11), 66 | > -0.45 | no, by less than its SE |
| guest-b | snapshot (epoch 5) | -0.43 (0.12), 65 | > -0.15 | no |

**Where the guest-b gap comes from.** I ran 40 more deals (seed 9158) with two labelled diagnostics on the snapshot model:

| guest-b model | 9a-32 minus 8p-32 (SE) |
| --- | --- |
| as in the run | -0.42 (0.17) |
| without its card | -0.005 (0.0002) |
| house-gen5 alone, no card | 0.000 (identical to 8p-32) |

So with experience, all of the gap is the card's term added to the held nets' rows on their residual contexts: `read_calls` sets `with_card` when the reader takes a profile. That is bill's 0.35 to 0.6 nats for a full card on a matching profile. The mixture over the three nets costs nothing measurable here.

**Options:**
- **(A)** A shell setting whose default is today's behaviour, so the E9 jobs read exactly as before: the card's term is not added to a held net profile's rows, while the `card` profile keeps it. 9a-32's package sets it. This touches `bridge_harness/gen9.py`, your file. I would write it with a test on the arrival branch, rerun the bid-only check, and release on your thresholds. Going by the diagnostics I expect the snapshot near 0 and the arrival model near -0.3, the bound being -log 0.70 = 0.36. About 45 minutes in all.
- **(B)** Run as is. Item 3 would then measure what the card on a matching profile costs at the table.

**Default under your 11:53 rule:** if you have not answered by 13:26, I do (A) on the arrival branch. I then send will the rerun check, written out, for a release; I will not submit on a failed check.

**Box time:** about 6.5 hours for 6,200 boards on azure4's 8 cores. That is from rehearsal 2's 33 CPU-seconds a floor board and 21 for other boards, plus about 5 seconds a floor board for item 6, assuming azure4's cores are like this machine's.
