# Additional Gen6 fast self-play

User instruction: only Gen6 fast versus itself, with latest Gen7 capture. This is a separate 25,000-family cohort. Do not run BEN, medium, or old-bot matches. Gen3 is retained solely as the existing tie-audit reference.

Source: `/workspace/scratch/43350986bc04/gen6-selfplay`.
Run: `runs/fast-only-20261111`.
Feed: `arena-gen6-extra-selfplay-feed` in maxschireson/Single-Dummy-Bridge.
Manifest: `55f11f996cfb2846436a68246e17819f5fff5fadd7030335bd2f1df5df82255c`.

All 43 engine modules match GitHub capture source b81d674d983e2bb3b158400192a82c41177fde55. Real-model capture/control preflight is stored with the run. Actor/model hashes and seed are frozen in its manifest.

Run `.venv/bin/python -u launch_selfplay.py` from the source directory. Inspect `.supervisor.lock` and `.writer.lock` first: never duplicate a live writer. STOP means intentionally stop; do not remove it automatically. Failures require inspection. A fresh heartbeat and increasing receipts establish live progress; a committed snapshot is historical.

Publish by reading `publish_feed.js` and executing it as an async function with `tools,text`; it uses authenticated GitHub tools. The snapshot contains full episodes, receipts, corpus, models and pinned runtime, plus normal arena exports. It verifies hashes before and after publication. Do not modify other producers or their feed branches. The dashboard registry key is `gen6extraselfplay`.

If restoring elsewhere, copy `recovery/runtime` to a new source directory and `recovery` run artifacts to `runs/fast-only-20261111`, install the original TensorFlow/NumPy/SciPy environment, verify DDS compatibility and all manifest hashes, and resume only after confirming the old writer is gone.

## Observed interruptions — 11 November 2026
The first two launches stopped without STOP, recorded game failure, or a traceback, after roughly nine minutes of collector activity (57 and 106 total boards). Both writer and supervisor locks were free at inspection. Cause is unconfirmed; do not describe the worker as continuously running. At the second recovery it was resumed in a PTY exec session (89092), retaining the same frozen runtime and manifest. Verify fresh receipts and locks on future checks.

At the 10:20 Lisbon check, collector was stopped at 159 receipts, no STOP or failure and both locks free. Resumed in PTY session 27333. Publisher inventory reads are now paginated to avoid output truncation as the cohort grows; frozen play/runtime/manifest unchanged.
