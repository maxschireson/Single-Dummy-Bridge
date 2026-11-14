# P02: the perf patches measured on Zen 4 (PR #35, approved by loop with a 3 box-hour budget on Bridgebots7)

`setup.sh COMMIT` prepares `~/perf` on a fresh box (venv with numpy 2.5.4 and torch's CPU build as the loop's venv-t,
DDS, the claim solver, the capsule's recovery folder, round 4c's net). `run_ab.py` then plays every configuration twice
on seed 777, deals 0 to 99, one worker a run, eight runs at a time (at most four unpadded-bf16 runs at once, for memory),
and writes `~/perf/ab/report.txt`.

| Config | Pair | Precision | Patches on |
| --- | --- | --- | --- |
| stu-base | stu4c-psta~stu4c-pstb | bf16 | none (as collected now) |
| stu-buckets, stu-forks, stu-features, stu-policy | the same | bf16 | one each |
| stu-forks2 | the same | bf16 | forks by the old path on the fork stream: the card reference for stu-forks |
| stu-all, stu-all2 | the same | bf16 | all four; stu-all2 with forks as stu-forks2 (stu-all's card reference) |
| g8-base, g8-features, g8-policy, g8-all | g8-greedy0~g8-passive0 | fp32 (as collected) | none, one, all |
| g8-bf16-all | the same | bf16 | all (a proposal: bf16 changes Gen 8's cards) |

Measured per run: CPU-s a board, boards an hour of one worker, peak worker memory over the run. Cards: each run against
both runs of its reference configuration, and the reference's two runs against each other (the run-to-run floor).
Padding and fork batching do nothing for the fp32 Gen 8 engine (no bf16 calls, no rollout forks), so they are not
measured alone there.
