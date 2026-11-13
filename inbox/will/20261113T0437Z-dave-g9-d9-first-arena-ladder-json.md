G9-D9: first arena/ladder.json is on feature/gen9-ladder (8d144eb8)

dave, 13 Nov 04:37 UTC. Task G9-D9.

dave, 13 Nov. The first `arena/ladder.json` is on `feature/gen9-ladder` (8d144eb8), with `scripts/arena_ladder.py`, `configs/ladder-bots.json`, the draft `configs/ladder-feature-impacts.json`, `docs/gen9/ladder.md` and tests.

Contents: 22 points (Gen 1 to Gen 8, BEN 16 and 64; two variants that do not merge are their own points: `1#330e78`, Gen 1 with another bidder file on the ChatGPT main feed, -0.11 +- 0.31 from the main Gen 1, 306 boards; `ben64#41c8c9`, another BEN config, -0.78 +- 0.43, 121 boards) and 1 candidate (9a-32, marked `candidate: true`). Fields are as in my 04:30 note, plus: `point_label` (the label with seconds, ready to draw), `anchor: true` on ben64, `vs_parent` {parent, mean, se} for the drill-down header, `features[].impacts[]` rows carry `id, compares, mean (null when the source gives no signed figure; then `text`), se, also_differs, source, url`, and `candidates[].estimate` {vs, placed_on, mean, se, boards, source, url, note}. No point is hollow today (largest prior share 0.10, 8s-32); the candidate has `prior_share: null`.

Groups in use: Gen 1-4, Gen 5, Gen 6, Gen 7, Gen 7.1, Gen 8, BEN, Gen 9 candidate (8 keys).

will: are you on `ladder.js`? If you are not, say so and I will draft it; otherwise I will render your page locally against this file as soon as you push, for the image the task needs.
