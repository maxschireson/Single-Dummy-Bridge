Re cohort: yes, apply the two SSH config lines now; job file updated

dave, 13 Nov 06:52 UTC.

dave, 13 Nov. Yes please: apply the two config lines to ~/work/g9/runs/g9-cohort-azure4/publication now through boxctl (remote to git@github.com:..., core.sshCommand with the boxctl key); the running publisher retries every minute and should push on its next pass. I replaced g9-cohort-azure4.json: progress count files, and env BRIDGE_FEED_REMOTE and GIT_SSH_COMMAND for any new checkout; no restart needed for the running job. BEN pair: I will send its job file with the main job's resubmission at 5 workers in one go, once you say the BEN 64 lane can run the collector (ops/run_gen9_cohort.py) inside its namespace; the lanes tool runs gen9_match.py today, so that part is yours to judge.
