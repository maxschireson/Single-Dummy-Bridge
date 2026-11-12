# Contributing

Read [onboarding](docs/onboarding.md) and [current system](docs/current-system.md).
Start new work from `main`; keep deployed runs on their frozen revisions.

## One change, one destination

- Open a scoped branch from `main` and target `main` with the PR.
- Use `feature/`, `fix/`, `research/` or `docs/` names for new source work.
- State the concrete problem, affected subsystem and completion criterion.
- Prefer one issue for an unresolved decision; do not leave completed launch PRs
  open as a progress log.
- Stack PRs only when the dependency is explicit. Retarget or close successors
  after integration so the review queue reflects actual work.
- Feed, transfer and archive branches are artifact/provenance stores. Do not
  merge them into source or delete them as routine branch cleanup.

## Research handoff

Record source commit, configuration, model hashes, dataset/family splits, metric,
sample count, uncertainty and artifact locations. State whether the evidence is
prediction, double-dummy proxy or played results. Include negative/inconclusive
outcomes. A model change needs its release/provenance updated; a cohort change
needs a new manifest. Do not relabel old observations as a new bot.

## Keep the structure usable

| New material | Destination |
| --- | --- |
| User/contributor explanation | `docs/`, linked from `docs/README.md` |
| Generation launch notes, closeouts | `docs/generations/genN/`, linked from its page |
| Experimental result | Dated path in `reports/`, linked from `reports/README.md` |
| Reusable engine logic | `bridge_harness/` with relevant tests |
| Offline build/train/analyze command | `scripts/` |
| Collector supervision/recovery | `ops/` |
| Versioned recipe | `configs/` |
| Released model | `models/` with restore instructions and hashes |
| Bulk records/checkpoints | Dedicated feed/transfer artifact location with a manifest |

Update [current system](docs/current-system.md) when the adopted system changes.
Update [backlog](docs/backlog.md) when a listed disposition changes.
Generation-specific documents go under `docs/generations/genN/` (the current generation's
may stay at `docs/` root until its closeout); a generation change triggers the
[generation cleanup](docs/generation-cleanup.md).
Avoid new root-level status dumps and append-only README narratives.
Historical documents retain dates; add a supersession link when they could be
mistaken for current operational instructions.

## Validation

Run checks appropriate to the change. For docs, verify file links and quoted
commands. For source, run relevant tests and report dependencies/skips honestly.
For arena/reporting changes, verify immutable identities, deduplication, replay,
and separation of common/native conditions. Preserve the observation boundary.

The repository cleanup preserved Gen6 runtime files byte-for-byte. It checked a
two-board dependency-light match/replay and 11 core tests; it did not rerun all
native DDS, TensorFlow or BEN integration tests.
