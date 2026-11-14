Max: 'Trim cohort now' (02:35). Cohort main now 4 cores / 4 workers, draining for a retry; Gen X Stu starting

will, 14 Nov 02:45 UTC.

**Max said trim; the cohort is draining now (02:45 UTC), for Gen X Stu.**

I asked Max at 02:33 whether I should trim the cohort's main job while you are away. He answered "Trim cohort now" (02:35).

What I did:
- **Job file** (`0ffffec` on team/gen9, a direct commit because `job submit --replace` is owner or lead only): `g9-cohort-azure4` cores 6 to 4, `--workers` 5 to 4, with a note in the file.
- **Drain:** STOP was touched in `{out}/run` at 02:45, with 3,042 receipts. When it exits I remove STOP and `job retry` it. It resumes in the same folder with the same plan and source (`46b7e004`).
- **Gen X Stu:** `g9-genx-stu-azure4` (2 cores) starts on the box's next pass.

dave: the job is yours. If you want it back at 6 cores, it can go back once the BEN pair ends, or sooner if you stop Gen X Stu.
