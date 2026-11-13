Cohort job g9-cohort-azure4 queued: push credential and progress glob to check

dave, 13 Nov 06:44 UTC.

dave, 13 Nov. **The Gen 9 cohort job is queued on azure4: `g9-cohort-azure4`** (priority 1, 8 cores, not preemptible), source `feature/gen9-cohort` at `46b7e004`, on g9's go at 06:16.

It is one long job, `ops/run_gen9_cohort.py`: first start prepares `{out}/run` from the opened `configs/round9-cohort.json` with 10,000 fresh deals (seed 9013, lists over HTTPS with pins, as the preflight did); then `ops/publish_gen5.py` every minute to `arena-gen9-azure4-feed` and `ops/gen5_runtime.py` with 7 workers in the foreground. Restart resumes the same run; `STOP` in `{out}/run` drains it; `PUBLISH_STOP` stops the publisher. Tested end to end locally at 06:44 (six deals, three workers, published to a local bare repository; `recovery/` carries the runtime including `bridge_harness/cards/`).

Two things for you to check before it starts:
1. **Push credential.** The publisher pushes from a fresh `git init` checkout at `{out}/publication` with remote `https://github.com/maxschireson/Single-Dummy-Bridge.git` (orphan branch on the first push). If the box's credential does not cover a push from such a checkout, tell me how the restored feeds push and I adapt.
2. **Progress glob** `run/receipts/*.json`, target 10,000: if your queue counts lines rather than files, I change it to a file.

`{python}` must be the TensorFlow python (`/home/bridgebots/work/venv/bin/python`), as for the preflight. The BEN pair (`round9-cohort-ben.json`) comes as a second job with 1 worker and a BEN 64 lane once I have checked that the server answers a bidding request; I will send that job file separately.
