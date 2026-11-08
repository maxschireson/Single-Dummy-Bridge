# Strategy cost, information states and small endings

8 November 2026. Follow-up to [the pilot experiments](consistent_strategies.md).
The [information-state design](../docs/information_strategies_partitions.md) specifies
proof scopes, actor views, strategy consistency, and the next learned-belief /
learned-selector experiments. Attribution is in [CREDITS](../CREDITS.md).

## Decision

The current alpha-mu ending hybrid and rollout planner do not earn their extra
compute in the larger experiment. Keep them as research references and sources
of executable strategy examples. The next playing-strength experiment should
improve PIMC beliefs and learn selection among equal or near-equal candidate
plays, with belief-only, selector-only and combined ablations. No trained
network or measured neural improvement is claimed here.

## Quality per extra compute

For a candidate taking more compute than its baseline, the requested grade is:

`(candidate tricks/board - baseline tricks/board) / log2(candidate compute / baseline compute)`.

Compute is summed declarer-policy process CPU time per complete board, including
planning and continuation. It excludes player construction, shared defenders,
and common opening-lead selection. Wall time is also measured and gives similar
ratios here. CPU time avoids scheduler delays being misinterpreted as algorithm
cost while six workers share the machine. This is not a hardware-independent
latency claim. Ratios use totals, not an average of per-board ratios.

The 1,000 boards comprise 500 independent deals and 50 fixed-NS families with
10 EW allocations each. All five configurations play every board against the
same greedy defenders, with the same opening lead and trick objective: 5,000
completed, legality-and-score-replayed tables. Full-hand PIMC seeds are coupled
across PIMC-8, PIMC-16 and the alpha-mu hybrid; execution order rotates. The
planner searches one nonforced declarer decision using eight outer hypotheses,
a fixed greedy defender model and a PIMC-2 continuation. Its matched control
executes that identical continuation without planning.

Approximate 95% intervals use 2,000 paired cluster-bootstrap replicates, preserving
whole related families and the designed broad/related cohort mix. They are
pointwise intervals, not a multiple-comparison-adjusted promotion test.

| Candidate vs baseline | Gain tricks/board (95% interval) | CPU ratio | Gain per time doubling (95% interval) |
|---|---:|---:|---:|
| Alpha-mu-8 ending hybrid vs PIMC-8 | -0.012 [-0.023, -0.001] | 1.083x | -0.105 [-0.202, -0.008] |
| PIMC-16 vs PIMC-8 | +0.039 [-0.016, +0.092] | 2.029x | +0.038 [-0.016, +0.089] |
| Planner-8 / PIMC-2 tail vs Matched PIMC-2 continuation | -0.006 [-0.057, +0.047] | 13.372x | -0.002 [-0.015, +0.013] |
| Planner-8 / PIMC-2 tail vs PIMC-8 | -0.308 [-0.378, -0.236] | 3.478x | -0.171 [-0.211, -0.130] |

| Configuration | CPU seconds per board |
|---|---:|
| PIMC-8 | 0.537 |
| Alpha-mu-8 ending hybrid | 0.581 |
| PIMC-16 | 1.089 |
| Matched PIMC-2 continuation | 0.140 |
| Planner-8 / PIMC-2 tail | 1.867 |

Cohort results show that the pooled result is not hiding a successful related-layout variant:

| Candidate vs baseline | Independent deals: gain (95% interval) | Fixed-NS families: gain (95% interval) |
|---|---:|---:|
| Alpha-mu-8 ending hybrid vs PIMC-8 | -0.014 [-0.034, +0.004] | -0.010 [-0.020, -0.002] |
| PIMC-16 vs PIMC-8 | +0.044 [-0.034, +0.122] | +0.034 [-0.044, +0.110] |
| Planner-8 / PIMC-2 tail vs Matched PIMC-2 continuation | +0.002 [-0.072, +0.078] | -0.014 [-0.090, +0.064] |
| Planner-8 / PIMC-2 tail vs PIMC-8 | -0.282 [-0.378, -0.188] | -0.334 [-0.442, -0.230] |

Alpha-mu wins 7 boards, loses 17 and ties 976 against PIMC-8 on tricks. Its
1,158 plans execute 4,393 later policy actions. There are 362 out-of-sample
observations on 356 boards and no search-budget fallbacks. The eight sampled
layouts are not a complete information set. This experiment does not isolate
the loss caused by incomplete support from the effect of pessimistic omniscient
defence or changed tie-breaking. Exactness for the sampled model is not a
guarantee of stronger play against the actual greedy defenders.

Doubling PIMC samples has a positive point estimate but its interval includes
zero. The planner has no established advantage over its continuation and is
clearly behind PIMC-8. The earlier 100-board positive estimates did not persist.
These synthetic contracts and weak defenders do not establish tournament strength.
Related layouts assess this important input distribution; this revision does not
implement cross-board proof-cache reuse.

The per-doubling grade is a finite-difference slope, not a law that the gain
repeats for further doublings. Report absolute gain and time alongside it.
For ratios at or below one, use dominance/tradeoff comparisons; for uncertainty
crossing one, suppress the grade interval rather than divide by an unstable budget.

## Double-dummy table sizes versus single-dummy knowledge

At a trick boundary, equal-sized hands with fixed leader and strain have
`52! / ((52-4k)! (k!)^4)` raw allocations. The independent counting script
preserves only relative ranks in each suit, normalizes the leader by rotating
seats, and applies suit permutations (all four in NT, three nontrumps otherwise).
Burnside counting handles stabilizers exactly. One NT table plus one canonical
trump table covers all strains; no extra factor of five is needed.

| Cards per hand | Raw allocations, fixed leader/strain | States after specified symmetry | Ideal values-only storage |
|---|---:|---:|---:|
| 3 | 76,277,828,779,152,000 | 39,552,072 | 9.43 MiB at 2 bits/value |
| 4 | 653,534,134,886,878,245,000 | 12,881,180,760 | 4.50 GiB at 3 bits/value |

These are exact counts for that normalization, not a minimum representation.
They include no lookup-index, action or metadata overhead. A four-bit format
would use 18.86 MiB and 6.00 GiB respectively. Mid-trick queries can search to
the next boundary; those intermediate states are not included in the table.

Stone, Sturtevant and Schaeffer (IJCAI 2025, Table 2) report **double-dummy**
set databases of approximately 0.001 GiB for 12 total cards and 0.05 GiB for
16 total cards: about 1 MiB and 51 MiB. They use additional equivalences and
verified sets, so their sizes are not measurements of our normalization or code.
This is strong evidence for pursuing semantic grouping, but a shared DD value
does not prove the existence of one information-consistent strategy.
https://www.ijcai.org/proceedings/2025/0995.pdf

For a fixed declarer hand, dummy and unseen pool, there are at most 20 defender
allocations at three cards each and 70 at four. Arbitrary subsets number 2^20
and 2^70 (about 1.05 million and 1.18e21). Those are mathematical subset counts,
not claims that every subset is a reachable information state. Histories,
belief weights, defensive knowledge and opponent models add distinctions.

Continuous beliefs need not be enumerated: a complete achievable frontier for
a fixed domain and response model can be reweighted. A strategy on a smaller
support extends to the full domain with zero mass elsewhere. The guarantee does
not extend to unexamined layouts or changed observation/defender assumptions.

## A finite semantic-partition experiment

For 100 fresh three-card families, all 20 EW allocations are enumerated, with
fixed declaring hands. All five strains are represented. Every retained root
policy is executed against every legal defender reply in every domain member.
No DD leaf values substitute for executable continuations. This is the
deterministic-declarer, omniscient-adversarial-defence model.

| Measurement | Result |
|---|---:|
| Completely verified worlds | 2,000 |
| Retained strategies across families | 247 |
| Strategies per family, mean / maximum | 2.47 / 64 |
| Families needing only one retained strategy | 78 / 100 |
| Outcome cells per strategy, mean / maximum | 5.60 / 14 |
| Strategies with a single outcome cell | 55 |
| Policy DAG nodes per family before / after equal-suffix sharing | 703.42 / 236.86 |
| Compressed witness payload, mean / maximum | 1145.01 / 3,611 bytes |
| Alpha-mu search time per family, mean | 0.148 seconds |

Cells use predicates such as ownership of a particular card or a suit-length
lower bound. They classify the outcome of one fixed policy; they never supply
a concealed fact to the actor. The partition rejects out-of-domain queries.
The exact root frontier is reweightable, including zero-weight sub-supports,
with tests comparing the answer to a fresh solve.

The compressed payload measurement interns identical policy suffixes, encodes
a JSON DAG and compresses it with zlib. Every payload is decoded and all policy
outcomes are reverified. It includes all retained policy witnesses for a family
but **excludes** card-domain keys, outcome vectors, model identifiers, proof
metadata and indexing. It is not a complete cache format or a global size estimate.
The 0.148-second search mean excludes certificate checking and encoding.

Outcome cells alone are not yet a demonstrated byte saving: twenty two-bit
values occupy only five bytes per policy, and predicate encodings can be larger.
The intended benefit is verified generalization across many families and reusable
policy structure. The current experiment verifies finite domains only; it does
not yet discover safe cross-family generalizations or measure cache hit rate.

## Reproduce and validate

Python 3.12.14, x86_64, repository DDS build; six processes for the full-hand
experiment. All 40 unit/system tests pass. Tests include independent tiny-game
policy enumeration, legitimate defender views, replay, full-frontier reweighting,
out-of-domain rejection, an independent one-card symmetry enumeration, and
paired/cohort-preserving cost statistics.

```bash
python3 scripts/build_dds.py
python3 -m unittest discover -s tests -v
python3 scripts/benchmark_cost_curve.py --count 1000 --workers 6 --seed 860001 --family-size 10 --out results/cost_curve_1000.jsonl
python3 scripts/benchmark_partitions.py --count 100 --out results/partitions_100.jsonl
python3 scripts/count_ending_symmetries.py
```

Use `--resume` for the cost study to keep completed rows; it also recomputes
the summary without replaying already completed boards. CPU timing will vary
across machines. The measured player logic is the prior reference implementation
at `cb20483`, with per-action CPU instrumentation added here; the new finite
certificates are benchmarked separately. Bulk datasets and logs remain excluded
from the source upload.

Raw-run SHA-256 identifiers for provenance:

```text
cost_curve_1000.jsonl  48b956672942261d97e84bd3ef103c71c32db2c14f360977ff8c54f369dd337b
partitions_100.jsonl   08d9f97f16557037765bcce1cb3e09b99741614de3a63762de751072ff164874
```
