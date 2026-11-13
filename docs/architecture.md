# Architecture

## A decision at the table

1. The harness creates an observation containing the actor's hand, exposed dummy,
   public auction/play, contract, vulnerability and legal moves. Actual hidden
   hands and the deal-generation seed do not belong in player inputs.
2. Gen6 builds possible hidden layouts. The opening lead uses the lead-belief net.
   Early play weights hand classes with the hand-fit scorer. Later play enumerates
   compatible layouts, bounded by the actor's configured limits.
3. DDS scores legal cards in each selected complete layout. The engine combines
   the estimates with their layout weights.
4. The retained Gen5 policy chooses among PIMC maximum ties. A unique maximum
   bypasses the policy.
5. The runner records the legal action, decision evidence and outcome. Paired
   comparisons, audits and publication consume those records.

These are single-dummy decisions built from double-dummy estimates. Sampling and
learned scoring do not eliminate PIMC strategy fusion.

## Code map

| Concern | Starting files |
| --- | --- |
| Rules and observation boundary | [core.py](../bridge_harness/core.py) |
| Gen6 decision logic and inference | [gen6.py](../bridge_harness/gen6.py), [gen6_nets.py](../bridge_harness/gen6_nets.py) |
| Original PIMC and BEN adapter | [players.py](../bridge_harness/players.py) |
| DDS binding and exact cache | [dds.py](../bridge_harness/dds.py), [dds_cache.py](../bridge_harness/dds_cache.py) |
| Gen5 representative layouts | [gen5r.py](../bridge_harness/gen5r.py), [layout_reduction.py](../bridge_harness/layout_reduction.py) |
| Policy outcome model | [policy_v5.py](../bridge_harness/policy_v5.py) |
| Bidding training | [bidding_loop.py](../bridge_harness/bidding_loop.py), [bidding_ppo.py](../bridge_harness/bidding_ppo.py) |
| Arena actors and records | [mixed_arena.py](../bridge_harness/mixed_arena.py), [gen5_arena.py](../bridge_harness/gen5_arena.py) |
| Pairing and audits | [arena_pairs.py](../bridge_harness/arena_pairs.py), [fork_audit.py](../bridge_harness/fork_audit.py) |
| Local match/replay CLI | [cli.py](../bridge_harness/cli.py), [runner.py](../bridge_harness/runner.py) |
| Runtime and supervision | [gen5_runtime.py](../ops/gen5_runtime.py), [watch_gen5.py](../ops/watch_gen5.py) |

Some filenames contain an earlier generation because newer actors reuse that
infrastructure. Follow dispatch/configuration rather than inferring behavior from
the filename. Existing paths remain stable for frozen source hashes and workers.

## Evaluation contract

Keep common-auction cardplay, native-auction total performance and paired
native-minus-common effects separate. Pool only compatible actor configurations
and bidder conditions. Deduplicate by canonical deal family and matchup,
independently of outcome. Training splits must keep related families together.
Audited branches and repeated snapshots are not new independent boards.

The [original architecture detail](generations/gen6/gen6_architecture_2026-11-11.md) describes
algorithms, switches and offline tests. Use [current system](current-system.md)
for active switch values.
