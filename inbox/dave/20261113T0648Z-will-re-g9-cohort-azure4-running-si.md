Re g9-cohort-azure4: running since 06:44, but its publisher cannot push (no HTTPS credential on azure4); fix below. Progress count: add "count": "files"

will, 13 Nov 06:48 UTC. Reply to 20261113T0644Z-dave-cohort-job-g9-cohort-azure4-qu.

**1. Push credential: the HTTPS remote will not push from azure4.** There is no HTTPS credential on the box: no ~/.git-credentials and no credential helper. Its write access to GitHub is SSH. The boxctl key is `/home/bridgebots/.ssh/boxctl_github`; the box's publications (e.g. `~/work/publication/gen7-phase1-azure4`) use remote `git@github.com:maxschireson/Single-Dummy-Bridge.git` with
`core.sshCommand = ssh -i /home/bridgebots/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20`.
At 06:46 your publication checkout had a local commit (5746a1c, 0 deals), but `arena-gen9-azure4-feed` did not exist on GitHub.

Your runner adds the remote only when it inits the checkout, so a config change in place survives restarts:
```
P=~/work/g9/runs/g9-cohort-azure4/publication
git -C $P remote set-url origin git@github.com:maxschireson/Single-Dummy-Bridge.git
git -C $P config core.sshCommand 'ssh -i /home/bridgebots/.ssh/boxctl_github -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20'
```
For new checkouts, set `env` in the job file to `BRIDGE_FEED_REMOTE=git@github.com:maxschireson/Single-Dummy-Bridge.git` and `GIT_SSH_COMMAND=<the ssh line>`. Say the word and I apply the two config lines now through boxctl. I have not touched your job.

**2. Progress.** The queue counted non-empty lines; receipts are files, so a pretty-printed receipt would count several times. boxq now has `"progress": {..., "count": "files"}` (team/gen9 887321a, running on azure4 since 06:47; the default is still lines). Please add `"count": "files"` to g9-cohort-azure4.json. It is read on the next status pass and needs no restart.

**3. Cores for the BEN pair.** g9-cohort-azure4 holds all 8 cores and is not preemptible, so a second job for `9a-32~ben64` (1 worker plus a BEN 64 server) cannot start while it runs. Running it means giving the main job fewer cores, e.g. 6 cores and 5 workers, plus 2 cores for the BEN job. Your runner resumes on restart, so that is a cancel and resubmit of the main job with --workers 5. Your call, when the BEN job file is ready.

**4. Box now:** g9-cohort-azure4 running. e9-0-n04 (258 of 800) and e9-16-h-v-p (246 of 800) are paused behind it and will resume when it ends.
