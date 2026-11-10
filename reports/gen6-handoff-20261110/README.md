# Gen6 training data handoff

This handoff indexes the complete raw records from all three Gen5 variants:
**Gen5, 5R and 5RZ**, across five physical run phases. Every source is pinned to
an immutable GitHub commit in [manifest.json](manifest.json). The original
compressed records stay on their existing publication branches; the inventory
identifies every file and its SHA256.

The download contains each run's **manifest.json, corpus.jsonl, episodes/*.json.gz
and receipts/*.json**. Episodes include the original complete main games,
counterfactual branches, per-action PIMC estimates, bidding decisions, actor
identities and final trick counts. Both common and native bidding conditions
are retained. Identical physical games referenced by both conditions remain
stored once.

The verified snapshot contains **11,115 paired records from 11,115 distinct
deal families**, with 154,950 completed cardplay tables, 58 passed-out games
and 6,178,469 actions with PIMC estimates. Its latest live-feed record completed
at **19:22:37 UTC on November 10, 2026**. Later records remain available from
the continuing live publication branch.

## Download

From this checkout, with Python 3 and Git installed:

```sh
python ops/fetch_gen6_handoff.py --out /path/to/gen6-inputs
```

The downloader uses sparse Git checkouts at the exact source commits, verifies
every compressed episode and receipt against the frozen SHA256 inventory, and
places the original records under:

```text
/path/to/gen6-inputs/<source_id>/manifest.json
/path/to/gen6-inputs/<source_id>/corpus.jsonl
/path/to/gen6-inputs/<source_id>/episodes/*.json.gz
/path/to/gen6-inputs/<source_id>/receipts/*.json
```

To fetch one phase first, add `--phase gen5-initial`, `--phase gen5-corrected`,
`--phase gen5r`, `--phase gen5rz-initial` or `--phase gen5rz-ben`. Repeating a
completed download verifies its files and continues with the remaining phases.

## Source phases

| Source ID | Variant | GitHub publication branch | Complete paired records |
| --- | --- | --- | ---: |
| gen5-initial | Gen5 | arena-gen5-codex-feed | 147 |
| gen5-corrected | Gen5 | arena-gen5-codex-32-feed | 6,607 |
| gen5r | 5R | arena-gen5r-feed | 2,552 |
| gen5rz-initial | 5RZ | arena-gen5rz-feed | 151 |
| gen5rz-ben | 5RZ | arena-gen5rz-ben-feed | 1,658 |

The live 5RZ-BEN feed continues publishing after this snapshot. Its branch head
can advance; use this handoff's commit for a reproducible fit, or audit and pin
a later complete batch. Closed source phases are fully included.

The first phase includes 102 Gen5-192 versus historical-opponent deals that
were removed from dashboard statistics after the sample-budget correction.
Their raw games are retained for training. No Gen4 or 4p policy participant is
present; 4b remains eligible because it uses the older policy with the Gen4
belief model.

## Verification and training boundaries

`ops/audit_gen6_handoff.py` checked the published Git blob identity and compressed
SHA256 of every raw episode, matched every receipt, decompressed every record,
and checked canonical family, source split, participant identities, matchup,
auctions and swapped partnerships. Every main and branch cardplay table was
replayed to completion, with final score and declarer trick count checked.
Every non-forced harness decision has finite PIMC estimates. BEN uses its own
decision output; forced moves and replayed branch prefixes can omit estimates.
Passed-out auctions retain zero-score records and have no cardplay targets.

These are raw source records. The trainer must preserve provenance and apply
the full reserved-family union from the
[current Gen6 recipe](https://github.com/maxschireson/Single-Dummy-Bridge/blob/af2d7dc6d2ef72b95f23abe951e9f249c470d55b/configs/gen6-current-recipe.json)
before assigning training, validation and test splits. That includes
5RZ-BEN-100, DDSD and subsequent belief experiment reservations. A source
`train` label alone does not make a family eligible for fitting.

Merge this handoff with the recipe's existing historical/recent pool,
deduplicating canonical families, trajectories and branch records. The initial
192-record live-feed batch already used by the Gen6 training chat is a subset
of this handoff. Do not count those records twice. Use observed final outcomes
for played-action labels; preserve PIMC estimates as logged inputs rather than
treating unplayed estimates as observed outcomes.

Freeze each fit's input. Later arrivals accumulate separately for the final
unchanged-recipe fit from the same pinned Gen5 parent weights.

## Arena readiness

[configs/gen6-arena-readiness.json](../../configs/gen6-arena-readiness.json)
pins the recipe, parent weights and retained 5RZ behavior. The existing arena
continues collecting and publishing. Gen6 rollout awaits the three promoted
model artifacts. The requested 5RZ32/16 and 5R16/5-32 speed comparisons have
been cancelled and are not part of this handoff.
