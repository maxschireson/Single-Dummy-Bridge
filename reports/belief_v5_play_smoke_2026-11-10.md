# Dense v5 belief: bounded play smoke test

The selected current-size, consequence-weighted v5 belief checkpoint completed
50 fresh paired boards against 4b without runtime or replay failures. The result
was **−26 IMPs**, or **−0.52 ± 0.48 IMP/board (one standard error)**. This passes
the integration checks but provides no reliable conclusion about playing
strength. A longer arena comparison is appropriate for small differences.

| Check | Result |
|---|---:|
| Unique fresh deals | 50 |
| Swapped-partnership tables | 100 |
| Legally replayed card actions | 5,200 |
| Failures / passed-out boards | 0 / 0 |
| Candidate wins / losses / ties | 5 / 10 / 35 |
| Search layouts per decision | 32 |

Only belief weights changed. Both competitors used the same v3 policy and
bidder, near-tie threshold 0.125, zero exploration, and common per-ply random
streams. Auctions and contracts matched. Each candidate played both partnership
roles on each deal. Common/native regime outputs coincide and are counted once.
No extra branch audits were collected.

- Candidate: `99330ad3b1387a6fd8d78b297b3d1c915dbb67f5e9e624c871b997c0352fd37a`
- V4 belief reference: `b23eb37554a26abb5a5eaa03f547472c489abd00dd6f3c9b0cada96cc46eb7d9`
- Shared v3 policy: `8c62c88b0f2041ce78273e072d0b5530598255cc39b482826901ff1660e064f5`
- Frozen manifest: `234cb35ebb016fcbbfb2640d69bd0918735d52976d95dcd1966884c37e115a1c`

The independent seed was `202611100741`; generation rejected 110,569 known
families from the belief data, reserved pool, and component arena corpus. The
smoke cohort is separate from the reserved test set. The existing arena record
format assigns historical split tags to records; those tags do not imply these
fresh smoke deals were used in training.

The test stopped at its predeclared 50 boards. No attention run was restarted,
reserved test family evaluated, model promoted, or arena collection resumed.

Run directory: `runs/belief-v5-play-smoke-20261110`. Preparation and reporting:
`scripts/belief_play_smoke.py`. Execution:

```sh
python -u scripts/run_supplemental_arena.py \
  --run runs/belief-v5-play-smoke-20261110 --workers 2 --seconds 1800
```

The companion JSON contains all 50 family-level results. Raw play records,
frozen corpus, manifest and runtime hashes are retained in the smoke recovery
bundle. [Candidate model](../models/cardplay/gen5-belief-size-loss-2026-11-10)
and [training comparison](belief_size_loss_2026-11-10.md).

[Raw smoke records](https://chatgpt.com/library?file_id=libfile_fde3_f-0e39df3855488191bbd17ae989640e0f_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal)
(owner access required), archive SHA256
`c310598eebb030dfeeda0b542a116615b14ede9a749957251479b2361e8533b6`.
