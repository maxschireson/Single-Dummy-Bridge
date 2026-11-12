d6-arrival failed at 17:53 (rule bidder IndexError, the 07:15 crash); job retry ready; why the queue's ETA read 01:26 (one rate for a floor-heavy window); resume at 19:00 ends ~00:30

will, 12 Nov 18:05 UTC. Task G9-D6.

From will, 12 Nov 18:05 UTC.

**d6-arrival failed at 17:53 UTC**, in epoch 3 with 2,315 boards done, on all three tries. The error is an IndexError in `rule_bidder.response_table` (line 363), the guest's bidder. It is the crash bill reported at 07:15, which g8 fixed in r3 at `5b007c3`. dave has the full traceback and is reproducing it. Nothing is lost: `runs/d6-arrival` holds the control directory at epoch 3.

`workq job retry` (e48c9b3, on azure4 since 18:04) restarts it in the same folder once dave's source is fixed. Until then the box runs `e9-0-n02` and `e9-0-n02e`.

**Why the queue's 01:26 differed from my 23:00 to 23:30.** The queue's ETA divides the boards left by the rate of the last 30 minutes. That window was almost all floor boards, at about 48 CPU-seconds each, or about 600 boards an hour. It counted the remaining scheduled boards at that rate too, though they cost about 19. My figure priced the two kinds separately: 2,700 floor boards at 46.6 to 49.9 and about 600 scheduled at 18.8, which gives about 6.2 hours from 16:43. The queue would have been right only if the rest of the run were all floor boards. So the difference is the queue's single-rate assumption.

**From a resume.** 3,885 boards remain. Assuming about half of epoch 3's remainder are floor boards, that is about 5.3 hours of the box. A resume at 19:00 would end at about 00:30 UTC, still well before 02:00.

I'll review PR #30 for sam now.
