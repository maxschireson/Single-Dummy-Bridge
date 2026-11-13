Re G9-D9: page renders; refresh command; candidate date

dave, 13 Nov 04:53 UTC. Task G9-D9.

dave, 13 Nov 04:58 UTC. Rendered your page locally from the branch (headless Chrome, 1300 px): it draws and the labels do not collide. No changes from me; go ahead with the board note and gh-pages at about 05:20 unless someone objects.

Two small things on the data side, in `2c58fb79`:
- The 9a-32 candidate now has `introduced_utc` 2026-11-12T15:30Z (its activation in the arrival run). If you place candidates by `introduced_utc` when present it lands next to Gen 8 at 16:32; keeping it at `computed_utc` is also fine by me. Your choice.
- Its estimate is now written in `configs/ladder-bots.json` (the arrival run is frozen), so the refresh needs no control directory.

Hourly refresh (from a checkout of `feature/gen9-ladder`, about 1 minute after the first run, which fills the cache):
```
python3 scripts/arena_ladder.py collect --out ~/work/ladder/rows.jsonl.gz
python3 scripts/arena_ladder.py fit --rows ~/work/ladder/rows.jsonl.gz --out arena/ladder.json
```
then copy `arena/ladder.json` to gh-pages `arena/ladder.json`. The collect step reads gh-pages' registry and `reporting.js` itself, so a feed the dashboard registers appears at the next refresh; a new bot without an entry in `configs/ladder-bots.json` gets the weak prior, the group "other" and its feed's label. Tell me when one appears and I add its parent and group.
