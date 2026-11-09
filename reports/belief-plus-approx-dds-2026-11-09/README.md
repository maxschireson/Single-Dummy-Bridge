# Belief+ and approximate DDS experiment — 2026-11-09

Approximate DDS is the stronger first result: 5.63x lower focal-player CPU cost with an observed loss of 0.32 IMP/board. The interval still permits a substantial loss, so this is a promising development result, not evidence of equivalence. The larger joint neural evaluator regresses badly. No candidate is promoted to the arena.

## Completed results

200 independent held-out deal families, one frozen contract per family. Positive IMPs favor the candidate.

| Candidate | Total IMPs | IMPs/board | 95% paired interval | Focal CPU speedup |
|---|---:|---:|---:|---:|
| Joint neural, no DDS | -1,087 | -5.435 | [-6.124, -4.746] | 189.78x |
| Joint neural; exact DDS at 7 remaining | -743 | -3.715 | [-4.369, -3.061] | 46.31x |
| Approximate DDS; exact DDS at 7 remaining | -64 | -0.320 | [-0.893, +0.253] | 5.63x |

The intervals use a paired Student-t interval over the 200 family-level IMP differences. CPU speedups are total control CPU divided by total candidate CPU on the same predetermined 50-family subset. The timing pass recomputed every focal decision along each variant's recorded trajectory and verified every card and final score. It used process CPU time, one BLAS thread, and disabled persistent DDS caching. It excludes model construction, bidding and the unchanged opponent; it is not a measured end-to-end arena throughput multiplier. The wall-clock fields in `whole-games.json` came from concurrent jobs and are diagnostic only; use `cpu-timing.json` for comparative timing.

At the 1,000-node-per-move budget, the full-information screen gives:

| Tricks remaining | Positions | Exact DDS mean | Approximation mean | Speedup | Selected-move DD regret |
|---|---:|---:|---:|---:|---:|
| 13 | 190 | 35.83 ms | 2.05 ms | 17.48x | 0.183 tricks |
| 10 | 188 | 2.56 ms | 1.45 ms | 1.76x | 0.163 tricks |
| 7 | 176 | 0.31 ms | 0.72 ms | 0.43x | 0.009 tricks |
| 4 | 172 | 0.14 ms | 0.32 ms | 0.45x | 0.000 tricks |

This supports switching back to exact DDS late. These measurements cover 726 nonforced positions from 200 families. Speedups weight time spent, rather than averaging per-position speedup ratios. Regret averages across tied best estimated moves. The budget is per nonequivalent move, not per position. Full-information screening and whole-game screening reuse held-out families, so they are not independent confirmations.

The selected neural checkpoint is epoch 3. Early-position held-out test outcome cross entropy is 1.758, trick MSE is 1.626, and unknown-card owner accuracy is 55.53%. Early validation owner accuracy declined from 61.07% with the inherited encoder frozen at epoch 1 to 56.00% at the selected jointly trained epoch. This is evidence of task interference, though it does not by itself explain the playing-strength loss. Later epochs reduced MSE while worsening outcome cross entropy, so they were not selected. Training-to-NumPy export agrees within 2.87e-6 maximum absolute error. All 43 relevant tests passed.

## Neural model

The joint model has 1,202,372 parameters, versus 308,726 in its parent belief network and 39,512 in the Gen3 policy selector. A shared 768/384-unit encoder feeds a 52-card ownership head and a shared 128/64-unit action head producing a 14-bin remaining-partnership-trick distribution for each legal card. The auction/play encoder is initialized by function-preserving widening of the Gen4 belief checkpoint. One epoch trains the action head; subsequent epochs train jointly.

Inference inputs are exclusively the acting player's legal observation: visible hands, public auction and play history, contract, and each legal candidate card. There is no DDS baseline, DDS-derived input, hidden-card input, or DDS near-tie candidate filter. Ownership is supervised by the actual deal; action outcomes use actual frozen-bot continuations. Logged PIMC action differences provide an auxiliary training loss for alternatives without actual continuation labels. They are targets, never model inputs.

The loss is outcome cross entropy + 0.2 outcome mean squared error + 0.3 ownership cross entropy + 0.5 centered PIMC action-value mean squared error. The teacher term is an approximation to single-dummy action differences, and can carry PIMC biases. Branch outcomes and all action candidates are not interchangeable labels.

## Data and selection

All descendants, auction variants, and repeated plays of each canonical deal stay in one split. The existing modulo-10 rule is retained: 0 test, 5 validation, others train. There are 3,767 training, 479 validation, and 474 test families. Sampling caps each family at 128 distinct observation/action/outcome rows, with a 75% early-position quota where available. A total of 572,270 rows are selected from 3,289,947 distinct eligible rows: 457,308 training, 57,893 validation, and 57,069 test positions. Training contains 6,183,171 unknown-card ownership labels and 2,057,869 logged legal-action value labels. 72.8% of sampled positions are early (before ply 28). This is a first screen using the two locally available raw streams; it is not all historical project data. Earlier belief data is inherited through the parent checkpoint.

Checkpoint selection uses validation early-position outcome cross entropy. The six-epoch run was interrupted after four complete epochs; it resumed from epoch 4 with batch size reduced from 128 to 64 and a fresh Adam optimizer. The training log records that change. Test outcomes and match results do not determine checkpoint selection.

## Approximate DDS

The independent approximation uses two cheap perfect-information greedy rollouts to guess remaining tricks. DDS then attempts exact threshold proofs up to a node budget. Only completed proofs tighten the certified interval. At timeout, the rollout estimate is clipped to that interval and explicitly marked unproved unless both bounds meet. Heuristic estimates never enter the exact DDS transposition table or persistent answer cache.

The budget counts instrumented search visits, not wall time. It is per nonequivalent legal root move. A native implementation of the rollout avoids Python overhead. Interrupted search state is discarded, including the remembered-deal marker, so later exact solves rebuild their state. Legal equivalent cards share the same result. The full-information screen uses 200 held-out families and four stages, alternating complete/partial tricks. Bounds are checked against exact DDS for every evaluated move.

The prior 1,500-deal proof-ordering model predicted search-cost changes, not DD trick values. Its independent test showed approximately 0.0074% node savings and 1.16% more time. Its weights are not used here. It is a different prediction task from either the public-information model or an eventual full-information DD value net.

## Whole-game protocol

Frozen Gen3 is the control and opponent: 32 belief samples, original policy selector, and a 0.125-trick near-tie window. All variants maximize expected tricks for this screen, isolating architecture from the later IMP-utility choice. Auctions are frozen. One contract is selected deterministically per test family. The focal partnership varies by family hash. A fresh per-ply/actor random stream prevents skipping DDS from shifting later random samples. Results are paired against an independently replayed Gen3-vs-Gen3 control on the same deal and contract.

Variants: fully neural; neural until seven tricks remain, then Gen3 DDS; and approximate DDS with 1,000 search visits per nonequivalent move, the same 32 belief samples, and exact DDS at seven tricks remaining. The approximate player uses pure expected-trick argmax throughout, including its late exact-DDS phase; it does not retain Gen3's policy near-tie reranker. Thus its comparison includes that selector change as well as approximate per-world DD values. The neural hybrid uses the full original Gen3 late player. Candidate time excludes the unchanged opposing partnership. Full-information approximation speedups are separate from whole-game speedups.

## Reproduction

Build the native library with `python scripts/build_dds.py`. Use `scripts/prepare_belief_plus.py`, `scripts/train_belief_plus.py`, `scripts/benchmark_approx_dds.py`, and `scripts/evaluate_belief_plus.py`. TensorFlow is needed only for training; deployment uses NumPy. Frozen data is available as `Belief_Plus_Training_Data_2026-11-09.zip`, with hashes in its shard manifest. Run `python scripts/assemble_belief_plus.py --directory models/cardplay/belief-plus-2026-11-09` to reassemble the 17 parts and verify every SHA-256. The model and its manifest are in [models/cardplay/belief-plus-2026-11-09](../../models/cardplay/belief-plus-2026-11-09). The frozen baseline weight hashes are in `baseline-models.json`; the dataset identity is in `training-data.json`. Compressed complete game records and full-information input positions accompany this report.

The meaningful validation checks include hidden-card feature invariance, complete legal-action coverage, owner support through dummy play, certified bound containment across all partial-trick offsets, strict node-budget enforcement, exact-solver reuse after a timeout, and training/NumPy export agreement.

## Interpretation limits

A large number of positions is not the same as a large number of independent deals. Continuation outcomes were generated by stronger frozen bots; they need not remain calibrated after the neural bot controls future play. Ownership and action-value objectives can interfere. Logged action-value labels concentrate on historically evaluated alternatives even though deployment now considers all legal cards. Within-family deduplication keys use play history, chosen card, result and contract; identical trajectories under different auctions can therefore be collapsed, omitting some auction-diverse examples. This does not move data between splits. Whole-game confidence intervals are descriptive screening intervals. All candidates remain experimental.

## Next experiment

Keep the public-information belief net separate from a full-information DD value net at first. Train the latter on exact early-position DD labels, use it to replace the current greedy rollout estimate, and retain budgeted proofs plus exact late solving. The old proof-cost model is not a suitable trick-value initialization. Separately, test a frozen belief encoder or separate task adapters for the joint model, and train on the decisions and continuations it actually produces. Expand paired play before making an arena promotion decision.
