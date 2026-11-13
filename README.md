# Rollout net v1's training families, and the 8X v3 arena exclusion list

**Data, not a feed; never merge.** x8 session, 13 November 2026.

- `rollout-net-v1-training-families.json`: the deal families of every board in the 82 arena feeds rollout net v1
  was trained on (`transfer/rollout-net-v1-20261113:fetch.json`), read at the tips that fetch recorded, by
  `v1_families.py` (partial fetches; replay board files only). 21,509 families from 30,377
  boards; every feed has at least the episodes the fetch counted (30,377 boards against 28,275 episodes: the list can only
  leave out more than the training set, never less). Per-feed counts under `feeds`.
- `gen8x-v3-exclusions.json`: the list `configs/round8x-v3.json` is prepared with (`--exclude-families`): the union of
  that list and policy v4.1's (`transfer/v41-training-families-union-20261112`, 34,092), 50,818 families. sha256 72fafc4cce9ed62e6427b021103533e62e1bdfedc6acc96bf01c81186a88ee7a.

Max, 12 November 15:50 UTC: no bot plays a board in a family one of its nets was trained on; never in the arena.
