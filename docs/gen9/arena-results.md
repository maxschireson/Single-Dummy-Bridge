# The arena's results data: `arena-results-v1`

This is the data behind the arena's results page for a population (G9-D8). Today's page is built per generation: a hand-edited feed list (`gh-pages: arena/gen6-sources.json`), a fixed bot order, and one page per generation. The arena page is instead written from the arena's own state, at each epoch boundary, so nothing on it is edited by hand. Experiments are not on it; they have their own files.

- **Producer:** `bridge_harness/arena9_results.py` (`results_for_epoch`, `write_results`), from a control directory (`bridge_harness/arena9.py`).
- **Command:** `python scripts/arena9_page.py results --control RUN/control --players configs/players --reader 9a-32 --out DATA`. The arena runner writes the same files after each close.
- **Renderer (prototype):** `python scripts/arena9_page.py render --data DATA --out SITE`.

## Files

- `index.json`: `{schema, epochs: [n, ...], files: [...], latest}`.
- `epoch-<nnnn>.json`: the arena at the close of epoch n, one document per closed epoch.

A document never changes once its epoch has closed. History is the sequence of documents.

## `epoch-<nnnn>.json`

| Field | Content |
| --- | --- |
| `schema` | `"arena-results-v1"` |
| `epoch`, `condition`, `closed_utc` | The epoch; the rating condition (`native` or `common`); when the next epoch opened. |
| `source` | `epoch_manifest` and `next_manifest` (ids), `rules_version`, `source_commit`, `next_snapshot` (the experience snapshot handed to the next epoch). |
| `roster[]` | One entry per player ever registered: `player`, `kind` (house, anchor, synthetic, outside, guest) and `status` (candidate, active, champion, anchor, retired), as they stand for the next epoch. Also `version` (package sha, 12 characters), `identity` (bundle identity), `joined_epoch`, `admitted_epoch`, `retired_epoch`, `test` (`{champion, opened_epoch}` or null), and `declared` (`{card, carding}` names). |
| `ratings` | See below. |
| `decisions[]` | Registry events that take effect at this boundary, for the epoch after n; the first document also has those before epoch 1. Each has `seq`, `epoch`, `event` (submit, activate, open-test, promote, retire, champion), `player`, `author`, `authority`, `champion`, `evidence`. |
| `tests[]` | Each promotion test open during epoch n: `pair`, `opened_epoch`, `boards` (direct boards since it opened), `K`, `L`, `promote_at` (1/α), `futility_at` (1/β), `decision`. |
| `schedule` | `epoch`, `boards`, and `played`: `{purpose: {boards, pairs: {pair: boards}}}`, where purpose is one of floor, training, promotion, admission, panel. `next` holds the next epoch's `boards`, `purposes`, `pair_weights` and `floors`. |
| `learned` | `{player: {...}}` for players with experience, and every guest: what a Gen 9 bot is handed for the next epoch. The fields are `boards` (deltas), `deals` (distinct boards), `profiles_read` (`[[profile, p], ...]` after `believed`), `honesty_read` (`{situation: h, '*': pooled}`), `play_factor` (from `play.info`, or null), `off_card`, and `snapshot_matches_envelopes`. |
| `panel` | The fixed outside panel: `anchors` (players with status anchor), and `players: {player: {anchor: {cell, se}}}` for the version tracker. |

### `ratings`

The condition's ratings from every board so far. The rules are A4's: a deal family counts once per pair, earliest first, and a self-play pair counts nothing.

| Field | Content |
| --- | --- |
| `reference`, `t2`, `boards` | The reference player (rating 0), the pair-effect variance, and the boards counted. |
| `players[]` | Best first: `player`, `strength` and `se` (IMPs a board against the reference), `ci95`, `boards`. Also `field`, and `screen` (`won`, `lost`: opponents whose cell's 95% interval is clear of zero; `even`: the rest). |
| `field` | `{score, se, worst: {opponent, estimate, se}}`: the mean cell against the rest of the epoch's population, equally weighted (provisional until the field is set), and the cell with the lowest upper 95% bound. |
| `pairs[]` | Each pair that played: `pair` (i~j, from i's side), `boards`, `mean`, `se`. Also `predicted` and `predicted_se` (the leave-one-out prediction from the other pairs, with t2 re-estimated without the pair), `z`, `p`, `p_holm`, `testable` (prediction se < 1), `out_of_line` (Holm-adjusted p < 0.05), and `cell`, `cell_se`. |
| `cells[]` | Every ordered pair of rated players: `player`, `opponent`, `cell`, `se`. The cell is the precision-weighted mix of the pair's own result and the model's prediction, or the prediction alone if the pair has not played. |

## What changes for the dashboard

- **The feed list:** it comes from the arena's registry and the collectors' registrations, not a hand-edited file (docs/gen9/arena.md, migration).
- **The bot order:** it comes from the rating table, not a fixed list.
- **Pages:** there is one page for the population and one per player, not one per generation.
- **Collector freshness** (issue #13) would sit on the same page, from the collectors' heartbeats. It is not in this schema yet.

## Versioning

A new field is a minor change, and readers ignore fields they do not know. Renaming, removing or changing the meaning of a field means `arena-results-v2`.
