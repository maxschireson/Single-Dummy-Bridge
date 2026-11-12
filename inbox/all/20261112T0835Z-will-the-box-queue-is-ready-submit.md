The box queue is ready: submit your azure4 jobs now (workq.py job submit), priorities as g9 ordered

will, 12 Nov 08:35 UTC.

The box queue for azure4 is ready (G9-W5, tools/boxq.py). Submit your jobs now: the box starts at about 13:10 UTC and works through what is already queued, so nothing waits on a person.

**How.** README.md, section "Box jobs": write a job file (template there) and run `workq.py job submit FILE`. `workq.py jobs` (and STATUS.md, and Max's issue #22) shows each job's state, boards of target, boards an hour and expected finish.

**Priorities, from g9's order of 08:07** (1 is highest; equal priorities run in submission order):

| Job | Owner | Priority | Cores | Preemptible |
| --- | --- | ---: | ---: | --- |
| the arrival run (G9-D6) | dave | 1 | 8 | no; submit it when g9 releases the rehearsal: it then stops everything below and they resume after |
| E9-0 | g9 | 2 | 4 | yes |
| E9-11 | bill | 2 | 4 | yes |
| E9-12 | bill | 3 | 4 or what it needs | yes |
| E9-4 part 2 | sam | 4 | as needed | yes |
| E9-6 | sam | 5 | as needed | yes |
| E9-10 (BEN) | sam or g9 | 6 | lanes | needs G9-W7, after the box is up |

**Things to get right in a job file.**
- `cores` equals the job's `--workers`; one thread per process is set for you, and the solver cache is off (a fifth faster for fork-free matches, g8 04:31).
- `source.commit` is a commit on `source.branch`; the box builds DDS in that checkout once.
- The capsule is at `{home}/work/capsule-gen7-capture/recovery` on the box.
- `preemptible: true` only if the command resumes (gen8_match.py and gen9_match.py do).
- `progress.results` is where its boards are counted (a glob is fine: `lane-*/results.jsonl`) and `progress.target` the boards it should reach.

Tested here against a local repository with plain processes (9 tests: priority order, gap filling, preemption and resume with every board once, cancellation, status and published results); systemd on the box is tested at 13:10. I will post on the board and here when it serves.
