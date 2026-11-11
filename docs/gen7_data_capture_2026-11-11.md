# Gen 7 data capture: what to change in the collectors

11 November 2026. For the team controlling the Gen 6 workers.
Branch `transfer/gen7-capture-forks-20261111`, cut from `codex/launch-gen6-20261111` (`b34a40f`).

Max's decision (11 Nov): gather this now, in the same cutover as the match-mix change, accepting
fewer deals per hour. Tie audits stay at 50%.

## What to do

1. **Merge this branch** into the source the next cohort will pin. The runtime files it changes
   (`fork_audit.py`, `gen5_arena.py`, `gen6.py`) were byte-identical to the collectors'
   `recovery/runtime` copies when it was cut. As a patch it also applies cleanly to
   `codex/gen6-auto-ben-20261111`, `codex/gen6-ben-followups-20261111`,
   `codex/gen6-medium-ben-correction-20261111` and `codex/gen6-independent-collector-20261111`
   as they stood at 05:15 UTC on 11 Nov.
2. **Add one block to every plan** the next cohort uses (`configs/round6-codex.json`,
   `configs/round6-independent.json`, and any other):

   ```json
   "gap_fork": {"per_band": 2, "bands": [0.125, 0.5], "max_cpu_share": 1.5}
   ```

   `ops/prepare_gen6.py` and `ops/prepare_gen6_independent.py` check it and copy it into the
   manifest. Leave `audit` (probability 0.5) and `ben_audit` as they are.
3. **Cut over with the mix change**: drain, prepare, preflight, start, as for Gen 6. The manifest
   pins the source hash, so this needs a new cohort. Do not patch a running collector.
4. **Preflight** with `ops/smoke_gen6.py` as before. It now also checks every gap fork and the
   new log fields, and fails if gap forks are configured and none is played, or played without
   being configured.
5. **Equivalence check, once**: prepare a second run from the same source and the same plan
   without the `gap_fork` block, run the preflight on both, and confirm that root tables,
   audit-fork tables and `audits` match card for card (timing and the new fields aside).
6. **Report after the first 2,000 root tables** (see "First report").
7. **Confirm the ChatGPT feed is still collecting.** Its last episode on GitHub was 03:16 UTC on
   11 Nov; its last commit says the recovery archive is uploaded separately.

Not in this branch: the backfill on episodes already played (see "Backfill").

## What changes

### 1. Gap forks (`bridge_harness/fork_audit.py`)

Every fork today swaps the chosen card for an exactly tied one, because the reference selector
picks from the same eligible set. Gen 7 needs two things those forks cannot give: the search's
`estimates` in positions that follow an inferior card by a Gen 6 seat, and realized cost against
estimated gap.

After a root table and all its audits are finished, `collect_board` now plays up to
`per_band` forks in each gap band:

- **Eligible decision**: root table only; a committed Gen 6 search decision (the action has a
  `gen6` block) by either partnership; not forced; at least one legal card with
  `gap_to_best > 1e-9`. The opening lead counts. The card actually played is never a fork card.
- **Bands** by `gap_to_best`: (0, 0.125], (0.125, 0.5], (0.5, ∞).
- **Draw**, for each band in turn: take the eligible decisions that have a card in the band, draw
  `min(per_band, that many)` of them without replacement, and for each pick one of its cards in
  the band uniformly. Then shuffle the picks.
- **Stream**: `stream(seed, 'gap-fork', family, 'root')` only. The play and audit streams are not
  touched.
- **Fork**: recorded prefix, the forced card, then the same players on the same play streams.
  No audit and no further gap fork is drawn inside.
- **Budget**: `ForkBudget` is not charged. A fork runs unless the gap forks of this root table
  have already spent more than `max_cpu_share` × the root table's CPU. The check is against CPU
  spent, not against the fork's estimate, so an opening-lead fork is as likely to run as a late
  one. Picks stopped this way go to `budget_skips` with reason `gap-fork-budget`.
- **No gap forks on a board with BEN on either side**, as with `ben_audit`.

Records, only when gap forks are on:

- Fork table: `fork_kind: 'gap'`, `depth: 1`, node `root/gap/<ply>/<card>`. Its prefix actions
  are bare cards (`ply`, `seat`, `controller`, `player`, `card`, `replayed_prefix`); their search
  details are in the root table.
- `gap_forks` beside `audits` in each table record. One entry per fork: `parent_table`,
  `fork_table`, `ply`, `actor`, `chosen_card`, `forced_card`, `estimated_gap`, `band`,
  `band_edges`, `per_band`, `decisions_in_band`, `cards_in_band`, `propensity`,
  `realized_cost_tricks` and `realized_cost_imps` (root minus fork, from the side of the seat
  that played the card), `rollout_cpu`, `estimated_cpu`, `selection: 'gap-banded-post-commit'`.
  `propensity = min(1, per_band / decisions_in_band) / cards_in_band`.
- `compute.gap_cpu` in the table record; `gap_cpu` and `gap_fork_count` in the episode.

Gap forks are deliberately not in `audits`: `mixed_arena`, `direct_arena`,
`scripts/train_fork_policy.py`, `scripts/collect_policy_forks.py` and
`scripts/prepare_mixed_training.py` sum or assert over that list as ties against the reference.

### 2. Guess size (`Gen6Player.search_decision`)

Three log fields on every Gen 6 search decision, computed from solves already done. They
consume no randomness and do not affect the choice.

- `layout_best_utility`: the weighted mean of each layout's own best card.
- `guess_size`: that minus the value of the best single card for all layouts, in tricks. It is
  what seeing the layout before this one card would be worth; 0 when one card is best in every
  layout.
- `best_share` in each card's `estimates` entry: the weight of the layouts in which that card
  is a best card.

These are always on. Decisions that take the Gen 5 path inside a Gen 6 bot do not have them.

### 3. Plumbing

- `bridge_harness/gen5_arena.py` (`run_board`): reads `manifest['gap_fork']`.
- `ops/prepare_gen6.py`, `ops/prepare_gen6_independent.py`: plan block to manifest
  (`gap_fork_block`). Unknown keys and bad values are refused.
- `ops/smoke_gen6.py`: the checks in step 4.
- `ops/export_non_v4_policy.py`: skips gap-fork tables when validating a game.

## What does not change

- With no `gap_fork` block, or `per_band: 0`, records are as today apart from the three log
  fields.
- With gap forks on, root tables, audit-fork tables, `audits` and `ForkBudget` accounting are
  the same as with them off. Tests assert this with toy players and with the Gen 6 engine.
- `decision_timing`, the receipts' score fields, `validate`, `replay` and `ops/export_gen5.py`
  read root tables (or replay every table) and need no change. Receipt and state `tables`
  counts will rise.
- `ops/export_non_v4_policy.py` validates every table of a game. It now skips gap-fork tables
  there (counted as `gap_fork_tables_skipped`), since their prefix actions carry no estimates.
  Any other offline trainer that walks `tables[1:]` should skip `fork_kind == 'gap'` or treat
  it separately.

## Cost, from the live Codex feed

Sample: 164 non-BEN deals, 381 root tables (every sixth episode of the first 1,101).

| Quantity | Value |
| --- | --- |
| Root table | 7.65 cpu-s |
| Tie-audit forks today | 5.4 per root table, 0.23 cpu-s each, 16.6% of root CPU |
| Gap-eligible decisions | 12.8 per root table (23-episode sample, candidate seats only) |
| One gap fork at a uniformly chosen eligible decision | 0.71 cpu-s mean, 0.21 median (same sample) |
| Expected with `per_band: 2` | about 6 forks, about 55% of root CPU |
| Expected deal rate | about two thirds of today's |

Episode files grow by roughly half to two thirds: about six gap-fork tables, each around 0.6
of a full table, join the six full tables a root table has today. The feed branches grow with
them.

`per_band` is a first setting. With a root table costing about eleven gap forks, the usual
cluster-sampling optimum is √(11 × (1 − ρ)/ρ) forks per table, where ρ is the correlation
between forks of one table: 5 at ρ = 0.3, 10 at ρ = 0.1. The first report measures ρ.

## First report

After the first 2,000 root tables with gap forks:

- gap forks per root table, by band, and budget skips;
- added CPU as a share of root CPU, and deals per hour before and after;
- mean `realized_cost_tricks` against mean `estimated_gap`, by band and by phase (lead, tricks
  1–4, 5–8, 9–13), with deal-clustered standard errors;
- the within-table correlation of `realized_cost_tricks − estimated_gap`;
- the same table for the tie audits split into touching and non-touching card swaps, as the
  noise control below.

### Noise control already in the data

A fork's result differs from the root's partly because the continuation's layout draws differ
once the observation differs. Swaps between touching cards of one hand show how large that is.
On the 381 root tables above (2,075 tie forks):

| Tie fork | Phase | Forks | Result differs |
| --- | --- | ---: | ---: |
| Non-touching cards | tricks 1–4 | 216 | 13.0% ± 2.3 |
| Non-touching cards | tricks 5–8 | 461 | 6.1% ± 1.1 |
| Non-touching cards | tricks 9–13 | 586 | 0.2% ± 0.2 |
| Touching cards | tricks 1–4 | 144 | 8.3% ± 2.3 |
| Touching cards | tricks 5–8 | 275 | 3.6% ± 1.1 |
| Touching cards | tricks 9–13 | 372 | 0.0% |

So a gap fork's realized cost carries this much scatter before any effect of the card. The
selector's choice against the reference's on the same forks: +0.018 ± 0.029 IMPs per fork
(deal-clustered), which is no measurable difference.

## Backfill

Gap forks can be made for root tables already played, because `gap_picks` works from recorded
actions and a fork is a replay from the recorded seed. It needs each feed's frozen runtime,
manifest and artifacts to rebuild the players, so it is left to the team that has them:

- write sidecar files (`gap_forks/<index>.json.gz`, carrying the episode's `episode_sha256`);
  never modify an archived episode or receipt;
- first regenerate five archived tie forks and require card-for-card identity with the stored
  fork tables. Live forks reuse players whose caches are warm; a backfill starts cold, and this
  is the proof that it makes no difference to the cards;
- run at low priority beside the collectors, on its own publication branch.

## Conventions for Gen 7 training on these feeds

- Split by `family`. Records carry train/validation (validation is `int(family[:8], 16) % 5 == 0`).
  Hold out `% 10 == 0` as the test set, and neither train nor select models on it.
- A fork table's fresh decisions are those without `replayed_prefix` or `counterfactual_forced`.
- A gap-fork table follows one deliberately inferior card. Use its decisions as labels for
  positions off the best line; do not count its result as the root line's result.

## Verified, and not

Run here (no models, no BEN; DDS built from `vendor/dds`):

- `tests/test_gap_forks.py` (11 tests): bands, draw, propensity, fork structure, budget stop,
  manifest and BEN handling through `run_board` and `validate`, and that the guess-size logging
  changes neither the chosen card nor the existing estimates on 200 random decisions.
- `tests/test_gen6.py`: one new test drives gap forks from the Gen 6 engine's own estimates
  (toy nets, real DDS) and checks the root game is unchanged.
- `tests/test_gen6_launch.py`: one new test for the plan block reaching the manifest.
- Whole suite: 195 tests; the only two errors are the TensorFlow-dependent tests, which also
  fail on the unchanged base here for want of TensorFlow.

Not run here: `ops/smoke_gen6.py` on a prepared run with the real nets, the BEN lane, the
publisher, and steps 4 and 5 above. The cost figures are estimates from recorded episodes, not
measurements of this code.
