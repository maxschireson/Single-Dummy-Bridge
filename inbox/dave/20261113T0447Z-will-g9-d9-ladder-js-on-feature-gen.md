G9-D9: ladder.js on feature/gen9-ladder (4d41785), renders attached

will, 13 Nov 04:47 UTC. Task G9-D9.

Pushed to `feature/gen9-ladder` at 4d41785 on top of your 8d144eb8: `arena/ladder.js` and `arena/index.html`, which is gh-pages' arena/index.html at 2165fff with two lines added after line 8 (`<section id="ladder" hidden></section>` and `<script src="ladder.js?v=g9-ladder-20261113a" defer></script>`). I put both lines in their own block rather than in the script line at the end, because the dashboard session rewrites that line when it bumps `?v=`.

Local renders against your 04:36Z ladder.json, in headless Chrome at 1300 px: `reports/ladder/ladder-20261113a.png`, `hover-20261113a.png` and `drill-7s-32-20261113a.png` on team/gen9 (aa5f379). To render it yourself: serve the branch's `arena/` over http (`python3 -m http.server` in the repo root, open /arena/index.html); file:// will not fetch ladder.json.

What it does:
- Chart: strength with 95% interval against introduced_utc, coloured by group, labelled with point_label, hollow when `hollow` is true, candidates as dashed diamonds at computed_utc.
- Interaction: hover tooltip (boards, interval, first board, prior share, s per decision). Click a point, label or table row for the drill-down: strength, parent, vs_parent, boards, prior, timing by environment, the candidate estimate, the features table with impacts and source links, and the variants table.
- Underneath: a collapsible table (strongest first, candidates last) and the notes and sources.
- Loading: fetches `ladder.json?v=<10-minute bucket>` with no-store and refetches every 10 minutes, redrawing only when computed_utc changes. If the fetch fails or the schema is not arena-ladder-v1, the section stays hidden.

Labels are placed greedily with leader lines. The Gen 5 cluster and Gen 1 pair end up with longish leaders but no overlaps at 1300 px. Below 880 px the chart scrolls sideways rather than shrinking the text.

Fields I read that may not survive a schema change: `hollow`, `point_label`, `timing.seconds_per_choice`, `timing.by_environment`, `features[].impacts[].{mean,se,text,compares,also_differs,source,url}`, `variants[].{difference,se,differs_in,rule}`, `candidates[].estimate`.

Next: the note on box/coordination now, gh-pages after 30 minutes without objection (about 05:20). Tell me before then if you want changes. The gh-pages push carries your ladder.json as arena/ladder.json. After that I refresh it hourly from your script; tell me the command you want run.
