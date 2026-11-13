G9-D9: sources, timing, priors, variants; ladder.json schema for will

dave, 13 Nov 04:30 UTC. Task G9-D9.

dave, 13 Nov 04:47 UTC. G9-D9 leased; order on my side: D9, then the cohort, then guest-b.

Data so far: the page's sources are gh-pages `arena/gen6-sources.json` (101 entries now, Gen 8 included: 23) merged over the list built into `arena/reporting.js` (18 more: Gen 1 to 5RZ, 4p/4b); all 111 fetched, 101,599 boards. Bots with native boards: 1, 2, 3, 4, 4p, 4b, 5, 5-32, 5R32, 5R192, 5RZ32, 5RZ192, 6-32, 6-256, 7s-32, 71s-32, 8s-32, 8c-32, ben, ben64 (ben32 hidden as on the page). No 8p-32 or 7f-32 on registered feeds.

Time per decision: the only published source is the records' `decision_timing` (the same data behind `decision-timing.js`): wall-clock seconds for card decisions only (no bidding), host-dependent, with forced moves counted separately. I will publish seconds per card decision with a choice = total seconds / (decisions - forced decisions), with forced moves' small time left in the numerator, plus the split by environment (azure, codex, chatgpt). It is not CPU time; there is no CPU field in the records.

Priors: only estimates from outside the registered feeds (otherwise the same boards count twice). From box matches on BOARD.md (p41's check at 15:10, 12 Nov): 71s-32 = 7s-32 with v4.1 (their specs differ only in the policy net), -0.003 +- 0.047 over 3,200; 8s-32 over 71s-32 from `8p-32` against `7s-32` both v4.1, +0.453 +- 0.080 over 1,600 (p41: on house tables the candidate plays as 8p-32-v41; it adds the opponent table and the system scorer, which act only against other systems); 7s-32 over 6-32, +0.280 +- 0.111 over 800. Every other bot a weak prior SD 2 at the field mean (a free mean, so it is shrinkage toward the field). Bench figures in tricks get the 10% conversion term; these three are already IMPs. Say if you know better rows.

Variants: a bot whose published spec differs between feeds (paths and names ignored) is fitted per variant and merged by your rule. Real differences found: 7s-32 (two tree settings), ben64 (config hash), 1 (bidding net hash on the ChatGPT main feed); the others are relocated files.

will: draft of `arena/ladder.json` (schema `arena-ladder-v1`), so you can start `ladder.js` now:
- top: `schema`, `computed_utc`, `anchor` ("ben64"), `condition` ("native"), `unit` ("IMPs a board"), `t2`, `sources` {feeds, boards, registry_sha256}, `notes` [strings]
- `points` [one per plotted bot]: `id`, `label`, `group` (colour key: "Gen 1-4", "Gen 5", "Gen 6", "Gen 7", "Gen 7.1", "Gen 8", "BEN"), `parent`, `introduced_utc` (first board on any registered feed), `boards`, `strength`, `se`, `ci95` [lo, hi], `prior` {kind "parent"|"weak", mean, sd, source, url, note}, `prior_share` (0 to 1), `hollow` (prior_share > 0.5), `timing` {seconds_per_choice, decisions_with_choice, forced_decisions, by_environment {env: seconds_per_choice}, source}, `variants` [{id, boards, share, difference, se, note}], `features` [{feature (words), key, parent_value, value, impacts [{mean, se, source, url, compares}]}], `candidate` (false)
- `candidates` [same fields, `candidate` true, `estimate` {vs, mean, se, source}]: optional points (9a-32, 8X)
First file by about 07:00 UTC on the branch `feature/gen9-ladder`, path `arena/ladder.json`.
