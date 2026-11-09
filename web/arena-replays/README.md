# Board-level IMP links and two-table replays

The public arena supports drill-down from each net IMP total and comparison
matrix cell. Board lists sort by newest/oldest completion time, absolute IMP
swing, largest gain, or largest loss. Ties can be included. Clicking a board
opens the two actual root tables side by side, with card/trick navigation,
independent controls, autoplay, and a slider for each table. Each table shows its
own contract, declarer and auction, and can jump to the first different play.
Trick-history jumps also affect only their table. Deep links preserve separate
`ply1` and `ply2` positions; old `ply` links still set both initial positions.
Table-level contract/declarer/auction fields override the shared board fields;
older records fall back to the shared board contract.

The initial publication includes all 465 audited pre-migration direct pairs
(930 root tables). Live aggregates are currently published separately without
their card sequences; live links show that coverage gap explicitly. The
historical records are never substituted for the live cohort.

## Source and deployed paths

- Source: `web/arena-replays/` contains the static assets, exporter and tests.
- Public branch `gh-pages`: assets at `arena/replays/`, with a single script
  tag appended to the existing `arena/index.html`.
- Live data branch `arena-feed`: the running publisher should append replay
  exports at `arena/replays/` alongside `arena/data.json`.

The existing dashboard renderer, live feed, and statistics are unchanged. The
link adapter observes replacement rows and decorates the new scores after
each feed refresh. It preserves snapshot time, selected board window, cohort,
expected board count, and expected IMP sum in each link. The list checks its
published coverage against those values. A reverse matrix cell opens the
canonical matchup, whose first-named model sets the displayed IMP sign.

## Enable replay publication in the running collector

Run this before each live-feed commit, against the completed direct run:

```sh
python web/arena-replays/export_replays.py \
  --run /path/to/g0001-direct-cold \
  --output /path/to/arena-feed-checkout/arena/replays \
  --title 'Current direct matches'
```

Commit/push the resulting `catalog.json`, cohort `index.json`, and changed
`boards-*.json` shards to `arena-feed` with the normal feed update. Preserve
these files between feed publications. The viewer discovers that catalog
automatically and reads the corresponding raw GitHub JSON. No website rebuild
is needed for new play records. Keep the existing 60-second feed cadence.

The exporter reuses records whose receipt SHA256 is unchanged. A changed
committed episode that fails its receipt checksum raises an error. Files are
written atomically; complete root tables only are exported, with no audit
branches, neural diagnostics, or training examples. Each shard covers at most
100 indices (around 130 KB for the archived cohort). No full-archive transfer
is needed. Preserve cohort identities and do not flatten local indices from
different runs together.

When rebuilding the dashboard HTML, preserve this tag after its main script:

```html
<script src="replays/dashboard-links.js"></script>
```

Preserve the `arena/replays/` directory when updating `gh-pages`. The source
snapshot under `site/arena/index.html` is for local testing only; do not replace
a newer generated dashboard with this old aggregate snapshot.

## Export historical checkpoint

```sh
python web/arena-replays/export_replays.py \
  --archive /path/to/Bridge_Gen3_Final_Migration_3700_2026-11-09.zip \
  --output web/arena-replays/site/arena/replays \
  --title 'Historical direct matches · 465 boards'
```

Archive checksums and each episode's receipt hash are verified. Cards retain
their actual acting seat; a dummy play is displayed in dummy's hand. Model
assignments remain attached to N/S and E/W at each table. The replay engine
checks ownership, turn order, following suit, all trick winners, and the final
recorded declarer trick count before displaying a board.

## Validation

```sh
node web/arena-replays/tests/test_replays.cjs
python -m http.server 8766 --directory web/arena-replays/site
python web/arena-replays/tests/browser_check.py
```

The exhaustive replay test covers all 465 boards / 930 root tables and matches
the archived per-pair totals (AB −122, AC +22, BC −4). Browser tests cover
navigation and mobile layout when Chromium execution is available. The build
environment used for the initial publication blocked local Chromium startup
at its process-singleton socket; public-browser checks are performed separately.

“First different play” is an observational marker, not a causal attribution
of the IMP swing. All four hands are shown for the viewer; this is not a claim
that the playing bots could see hidden hands.
