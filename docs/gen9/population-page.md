# The arena as a population: page prototype (G9-D10)

Gen 9 (dave). A prototype for the page additions of [the self-play arena note](arena-selfplay.md) section 8,
built from the registered feeds; nothing here decides anything and nothing is on gh-pages yet.

```
python scripts/arena_ladder.py fit --rows rows.jsonl.gz --out arena/ladder.json --population arena/population.json
python scripts/arena_population_page.py --population arena/population.json --out SITE
```

`arena/population.json` (schema `arena-population-v1`) comes from the ladder's fit (same boards, priors and anchor):

- `cells`: every ordered pair of members, row minus column. A played pair is the precision-weighted mean of its own
  result and its leave-one-out prediction; an unplayed pair is the model's prediction with the pair-effect variance.
- `pairs`: each played pair's out-of-line test (its mean against its leave-one-out prediction, Holm-adjusted over the
  pairs whose prediction has an SE under 1 IMP).
- `members`: role (from `configs/ladder-bots.json`), field score against every other member equally weighted
  (provisional until Max sets the field), Nash average against a maximum-entropy equilibrium of the cells (point
  estimates), worst cell (the lowest upper 95% bound).
- `champion_against_panel`: the champion's cumulative native mean against each outside-panel member, by three-hour bin.
- `champion_boards_by_role`: the champion's native boards per three-hour bin by the opponent's role. The registered feeds
  have no epochs or purposes, so time bins and roles stand in for the training mix.

The page: members by role and strength, the cells heat map ordered by strength (rings for played pairs, a flag for pairs
out of line), the champion's field score, Nash average, worst cell, equilibrium and exploitability (not measured yet,
E9-23), its panel over time and its boards by role; one page per member with its cells grouped by the opponent's role.

Limits: the registered feeds declare bidding systems only and keep no experience, so a member's declared card and what
Gen 9 has learned about it are on the arena9 population pages (`scripts/arena9_page.py`, arena-results-v1) of runs that
keep them. The equilibrium uses point estimates; with few boards a member's cell can rest mostly on its prior (the
ladder's prior share says how much).
