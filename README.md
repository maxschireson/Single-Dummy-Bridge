# The arena's results page for a population: prototype (G9-D8)

This is a transfer branch: files only, never merged into source.

- **`site/index.html`:** the prototype page; open it in a browser. It shows the roster now, the ratings with intervals and field scores, ratings over epochs, the pair matrix, decisions by epoch with the promotion test's state, the schedule by purpose, and a tracker against the fixed outside panel. `site/players/<id>.html` is one page per player.
- **`site/data/`:** the data files the page is rendered from: `arena-results-v1`, one per closed epoch, plus `index.json`.

The data comes from `transfer/gen9-arrival-20261112` (c9cb575), the arrival run's control directory. The code is `feature/gen9-arena-arrival` (d029c7d):
- `bridge_harness/arena9_results.py`;
- `scripts/arena9_page.py results | render`;
- the format, in `docs/gen9/arena-results.md`.

Nothing on gh-pages changes.
