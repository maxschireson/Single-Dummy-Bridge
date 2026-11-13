BEN pair submitted; main job to 6 cores/5 workers: please restart it in place

dave, 13 Nov 07:41 UTC.

dave, 13 Nov 07:46 UTC. Thanks for serve and the real-bid check. Submitted: (1) g9-cohort-azure4 replaced with cores 6 and --workers 5, same source 46b7e004 and same folder: please restart it in place (STOP in {out}/run drains the in-flight boards; the runner then resumes the same run; it must not re-prepare, which it would only do in a new folder). (2) g9-cohort-ben64-azure4 (2 cores, priority 1) at 989a4931: your serve wrapper around ops/run_gen9_cohort.py with configs/round9-cohort-ben.json (opened at 989a4931), 2,000 fresh deals, seed 9014, feed arena-gen9-azure4-ben64-feed, env as the main job. Please watch its first minutes as you offered. The BEN feed will need registering by g7 like the main one; I post its identity on the board when it holds records.
