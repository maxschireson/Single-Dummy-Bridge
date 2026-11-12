Re E9-10 on BEN lanes: both done at 3cb55a0 (per-run tag in unit/namespace names; --ben-bot ben64 / --port); merge and resubmit with --replace

will, 12 Nov 12:32 UTC. Task G9-W7.

From will, 12 Nov 12:33 UTC.

Both are on `feature/gen9-workflow-ben-lanes` at `3cb55a0`, with tests (5 pass).

1. **Two runs at once.** Every unit and namespace name now carries a tag: `g9-ben-<tag>-<k>`, `g9-lane-<tag>-<k>` and `g9ben-<tag>-<k>`. The tag defaults to the `--out` folder's name in lower-case letters and digits. Under the queue that folder is `~/work/g9/runs/<job id>`, so your two jobs get `e910r9bben16` and `e9108xben16` and cannot meet. `--tag` overrides it; `status`, `measure` and `down` take `--tag` too. The queue has no "not with job X", so you don't need one.
2. **BEN 64.** `--ben-bot ben64` serves port 8089 with the capsule's `assets/ben-64.conf`. The default `ben` is 8087 with `ben-16.conf`, as before. `--port` and `--conf` override either. One limit: `install` checks only the BEN 16 model hashes of `configs/ben-gen5-16.provenance.json`. A BEN 64 run uses whatever models that pinned checkout holds, unchecked. If the capsule has a BEN 64 provenance file, tell me and I'll check those too.

To use them, merge `3cb55a0` into `feature/gen9-signals-v2` and resubmit both E9-10 jobs on the new commit with `job submit --replace`. That keeps their submission times. For a BEN 64 slice, add `--ben-bot ben64` to its argv; its pair names `ben64`.

On azure4, `w7-ben-smoke` (16 boards, 2 lanes, priority 1) runs right after the 13:00 deploy, and its lanes note follows. E9-10 can then run whenever the queue reaches priority 3.
