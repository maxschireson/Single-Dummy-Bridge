G9-D8 submitted: arena-results-v1 and the prototype page (transfer/gen9-arena-page-20261113)

dave, 13 Nov 04:10 UTC. Task G9-D8.

From dave, 13 Nov 04:12 UTC. Task G9-D8: submitted for review. Max asked about this directly at 03:39, and I answered him.

**What is done:**
- **The format:** `arena-results-v1`, written down in `docs/gen9/arena-results.md`. There is one document per closed epoch plus `index.json`:
  - roster (kind, status, version, declared card), and ratings with intervals, a field score and its worst cell, and a won/lost screen;
  - pairs against the leave-one-out prediction, with out-of-line flags (Holm), and cells;
  - decisions at the boundary, and the promotion test's betting state since it opened;
  - boards by purpose and the next plan;
  - what a Gen 9 bot has learned per player;
  - cells against the anchors.
- **The code** (on `feature/gen9-arena-arrival`, d029c7d): the producer `bridge_harness/arena9_results.py`; `scripts/arena9_page.py results | render`; and the runner, which now writes `control/page/` after each close. A synthetic run test checks the data and the render.
- **The prototype:** `site/index.html` and `site/players/<id>.html` on `transfer/gen9-arena-page-20261113` (99efe33), rendered from the arrival run's records. The page has the roster now, ratings, ratings over epochs, the pair matrix, decisions by epoch, the schedule and the panel tracker, plus one page per player. Nothing on gh-pages changed.

**One correction to the arrival page.** Its betting state counted the 69 direct boards of epoch 1, played before the test opened. Counted from epoch 2, as the new data does, it is 600 boards, K 1.19, L 0.67, no decision. Both are far from either threshold.

**What the dashboard session would need to adopt it** (to agree with them on the board):
1. Read `arena-results-v1` from a published place: a control branch's `page/` folder, or a feed the runner publishes. This replaces the hand-edited `arena/gen6-sources.json` for the arena page.
2. Take the bot order from `ratings.players` instead of a fixed list.
3. Render one population page and one page per player in its own style. The prototype is a reference for the content, not the code.
4. Keep the generation pages as they are for the frozen feeds. The arena page is a new page, not a change to them.
5. Collector freshness (issue #13) belongs on the same page, but it needs heartbeats in the data; that is not in v1. A v1.1 field is the clean way to add it.

**The guest-b follow-up** is still playing: epoch 5's floor records re-created so far all match the run's traces. On the first 50 deals, the opening leads were identical in every native table where the bot defended. I will send the split when epoch 5 is complete, around 05:00 UTC.
