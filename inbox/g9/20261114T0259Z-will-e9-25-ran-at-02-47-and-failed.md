e9-25 ran at 02:47 and failed: BEN keras layout (KeyError layers/dense/vars/0)

will, 14 Nov 02:59 UTC.

**e9-25 got a core at 02:47 UTC and failed in 3 seconds, three times. It is now `failed` and holds no core.**

**Why.** The positions step finished: `positions.jsonl` was written, with 5,124 positions from 2,730 native tables. Then `e925_study.py` stopped while loading BEN's net (journal of `g9-job-e9-25`, 02:49):

```
e925_study.py:52 ben_replay -> ReplayReader(path) (bridge_harness/cards/replay.py:38)
-> BenLstmBidder (system_bidders.py:86): g('layers/dense/vars/0')
KeyError: 'Unable to synchronously open object (component not found)'
```

The file `{home}/work/g9/ben/models/TF2models/GIB-BBO-8742_2026-10-23-E30.keras` has no `layers/dense/vars/0` in the layout `BenLstmBidder` reads. Either it is a different BEN file from the one the reader was written for, or the layers are named differently in it. I changed nothing.

**To run it again:** fix the reader or the path on `feature/gen9`, `job submit --replace` with the new commit, then `job retry`. With all 8 cores in use now, it waits for a free one.
