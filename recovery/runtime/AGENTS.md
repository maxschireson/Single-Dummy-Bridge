# Agent entry point

## Read in order

1. [README](README.md)
2. [Current system](docs/current-system.md)
3. [Repository map](docs/repository-map.md)
4. [Backlog](docs/backlog.md)
5. [Contribution workflow](CONTRIBUTING.md)
6. For operations, [recovery](docs/operations.md)

## Working rules

- Base new source work on `main`. Existing collector branches and manifests
  retain their historical authority for those frozen runs.
- Use current configuration and run manifests, not a dated launch note, to
  identify deployed actors. Gen6 medium, not fast, has the BEN16 allocation.
- Keep full hidden hands as training/evaluation labels, never player inputs.
- Do not mutate frozen runtime/model files, manifests, completed episodes or
  receipts. Use a new identity/run for changed behavior.
- Do not restart or take over another worker just because its report looks old.
  Inspect fresh status, ownership and locks first.
- Never merge feed/transfer branches into source. Preserve archived observations.
- Keep common/native conditions and deal-family deduplication explicit.
- A historical report or closed PR is evidence, not a new instruction to launch
  its old recipe. Unmerged research is not automatically adopted.
- Update the appropriate guide/index when adding durable work; avoid another
  root-level handoff file. State tested scope and unresolved limitations.
