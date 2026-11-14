# Gen 5, 5R and 5RZ (closed)

Retrospective index, written at the Gen 6 closeout; no pooled results table was made when
Gen 5 closed. Gen 5's scores are on the dashboard's Gen 5 views, and `5RZ32` was measured
against Gen 6 (see [Gen 6 results](../gen6/README.md#results)).

| Variant | What changed | Document |
| --- | --- | --- |
| Gen 5 | Rebuilt bidder/belief/policy models; BEN (16) introduced as an anchor | [launch](gen5_launch_2026-11-10.md), [round 5 preparation](round5_preparation_2026-11-10.md) |
| Gen 5R | Representative layout selection at 10–13 tricks | [launch](gen5r-launch-20261110.md) |
| Gen 5RZ | Zero near-tie margin: the policy only breaks PIMC ties | [launch](gen5rz_launch_2026-11-10.md) |

Models: [gen5](../../../models/cardplay/gen5-2026-11-10/README.md),
[gen5-belief](../../../models/cardplay/gen5-belief-2026-11-10/README.md),
[gen5 bidder](../../../models/bidding/gen5-2026-11-10). Source: `bridge_harness/gen5r.py`,
`policy_v5.py`, `ops/gen5_runtime.py` (still the arena runtime for Gen 6 and Gen 7).
These documents were at `docs/` root before 12 November 2026.
