Cohort running on azure4 since 06:44; its feed is not yet on GitHub (push credential), fix sent to dave

will, 13 Nov 06:49 UTC.

- **Cohort:** g9-cohort-azure4 (dave, 8 cores, not preemptible, 10,000 deals at about 300 an hour, so a little over a day) started at 06:44. Your e9-0-n04 (258 of 800) and e9-16-h-v-p (246 of 800) had started on the freed cores at about 06:18 and are paused behind it. They resume when it ends, unless you want them back sooner.
- **Feed:** its publisher pushes over HTTPS, and azure4 has no HTTPS credential (the box writes to GitHub over SSH with the boxctl key). So `arena-gen9-azure4-feed` did not exist at 06:46. Boards are being collected; only publishing waits. I sent dave the two-line fix, which survives restarts, and offered to apply it.
- **BEN pair:** with the main job holding all 8 cores, the `9a-32~ben64` job cannot start. I suggested dave run the main job on 6 cores (5 workers) plus a 2-core BEN job, a restart that resumes the run. His call.
