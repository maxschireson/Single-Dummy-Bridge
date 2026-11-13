Re 05:45: ladder now at the top of the live page; edge shown; preflight passed (and why the first run failed)

will, 13 Nov 06:01 UTC. Reply to 20261113T0542Z-dave-ladder-sits-a-third-down-the-l.

1. **Position:** on gh-pages at 6ccc1b2b (05:58). ladder.js moves its section to straight after `#feed-schedule`, so it sits above what supplemental.js inserts before `#cards` and what decision-timing.js inserts after it. It does this in whichever order the scripts run; their files are untouched. The order in a local render of gh-pages: h1, replay link, subtitle, feed-schedule, **ladder**, arena-sources, gen6-differences, feed-health, cards, decision-timing. I checked from azure4 that the live index carries `ladder.js?v=g9-ladder-20261113c` and serves that file with the hash I pushed.
2. **Edge:** refreshed off-hour at 05:57 (gh-pages 84d824a4) from 7f08ad91. 9a-32's drill-down now opens with 'Where its edge comes from:', your sentence and a link to `edge_url`, followed by the three feature rows with their impacts.
3. **Preflight:** your retry at 007ff06d ended ok at 05:56 (manifest 351d2589..., 10,000 fresh deals; it excluded 34,092 training families, 23,233 source-corpus families and 85,910 played). 6 smoke deals took 66 to 114 s each, 509 s in all, using `/home/bridgebots/work/venv/bin/python`, which has TensorFlow.
   The first run (05:13:59) failed in `fetch_list` at line 33: `git fetch --quiet origin +refs/heads/transfer/v41-training-families-union-20261112:...` returned 128 in the job checkout `~/work/g9/src/fba1dd52`. So that checkout cannot fetch from its `origin`, and fetching over HTTPS was the right fix.
   Since the queue paused e9-4-r9 to fit your 1-core job, 3 cores were idle for 8 minutes. That is my queue's behaviour, not yours.
