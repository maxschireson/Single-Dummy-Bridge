# Frozen v5 cardplay calibration — 2026-11-10

This experiment adds direct ACE cardplay and a time-calibrated BEN rematch. No model is promoted and all 100 evaluation deals remain excluded from training.

## Comparisons

- **BEN rematch:** same 100 deals, two auctions per board, bidders, models, room assignments and scoring as the original v5/BEN calibration. BEN remains a net-only bidder. Effort changes alone: BEN 16 sampled hands for cardplay and opening lead; v5 192 sampled layouts per nonforced decision. Timing pilots select effort using elapsed thinking time, not the IMP results.
- **ACE cardplay:** the identical frozen v5 bidder auctions all four seats. Both rooms replay exactly the same auction and contract, swapping v5 and ACE partnerships. Our v5 uses the same 192-layout setting. ACE uses one native thread, 1,000 ms search per nonforced play and 4,000 ms on opening lead, depth 4, exploration 0.0058, limiter off, and no iteration cap. Pilot timing supports these budgets; actual full-match timings are reported separately.
- Freeze: v5 policy attention epoch 4; dense belief current_consequence epoch 1; first bidding candidate play25_anchor002 (2,048 training pairs). SHA256 hashes and the original manifest are stored with each run.
- Scores: paired duplicate IMPs, positive for v5. Record both average IMPs and paired-board standard error / bootstrap confidence interval. One hundred boards is a calibration sample.

## ACE integration

ACE 1.0.5 `Ace.dll` comes from the pinned BEN runtime, SHA256 `cb88bf260aca279c984246a11e85e3bd36a2e8c3b618efecacc4b545d134b085`. Linux `libbcalcdds.so` comes from Ark223/ACE commit `d569392cb8192811ad9d2053ea9005c32bf1fc7c`, SHA256 `9a7ff26e47b1d46a077a99d1c842d9654959fec611ba23366b2baf51a8b7785b`. The public source at that commit identifies version 1.0.3; we do not claim the bundled 1.0.5 DLL was built from it. Its GPL license is included.

The adapter supplies only the acting side's visible original hands, the public auction via belief-derived constraints, and the public cardplay history. It never supplies hidden actual cards or a deal-generation seed. The adapter ranks ACE candidates by contract-success probability, then trick margin. The API enumeration is not best-first, and native CompareTo uses visits and depth, which often tie for every root candidate. Thirty-two v5 belief samples become broad ORIGINAL-hand suit-length/HCP min-max ranges, widened by one card per suit and two HCP. ACE searches its own sampled deals within those constraints. This is not equivalent to using our full card-location probabilities. ACE's native objective is contract success and trick margin; final match scoring uses vulnerability and doubles correctly.

Forced moves bypass search. A native search may overrun its time budget until an active native solve completes. Empty searches receive a recorded continuation; there is no fallback to a different cardplayer.

Validation passed: 1,040 public-information observations across all five strains and four declarer seats exactly matched the harness legal cards. On 35 fully known test-only positions at plies 24 or 39, every native candidate evaluation matched an independent DDS solve, including completed tricks and declaring/defending roles. The chosen move also matched the DDS-optimal value in all 35 positions. Full match records are independently replayed before counting scores.

## Timing and reproducibility

Timing is wall-clock time inside each player's decision, including belief preparation and BEN HTTP overhead, excluding process/model startup and bidding. Report total player thinking seconds per paired board and nonforced-decision mean/p95. Each player controls 52 cards across a pair of complete rooms. Native/BLAS/TF thread counts are set to one; persistent DDS cache is disabled. Room order alternates. Runs checkpoint every complete paired board and hold a writer lock; reruns skip completed boards and reject changed frozen inputs.

Run with the existing BEN Python environment (TensorFlow, NumPy and requests), Pythonnet 3.0.5 plus clr_loader, .NET 8, the bundled DDS libraries and the frozen model files. Set `BEN_ROOT` to a BEN runtime checkout if it is not at the original absolute path. The BEN revision is captured in the source manifest. `DOTNET_ROOT` can be supplied externally. Otherwise the script looks for `.NET` in `../dotnet`, Pythonnet dependencies in `../python-deps`, and native ACE files in `vendor/ace`.

```bash
export LD_LIBRARY_PATH="$PWD/vendor/ace${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
python -u scripts/calibrate_cardplay.py run --run runs/ben16-v5_192-100 --kind ben --v5-samples 192 --ben-samples 16 --workers 4 --port 18400
python -u scripts/calibrate_cardplay.py run --run runs/ace-v5_192-100 --kind ace --v5-samples 192 --ace-ms 1000 --ace-lead-ms 4000 --workers 4
```

After the manifest exists, its frozen settings take precedence over CLI defaults. `summary --run PATH` validates and reports completed records. `scripts/validate_ace.py` reruns the native integration checks. The timestamp values inside records come from the execution host; the human-readable experiment date is the user's session date.

## Timing pilot decision

On the first four pilot deals, BEN at 16 samples averaged 35.22 seconds per pair versus v5 at 64 samples at 8.53 seconds. Across eight prespecified pilot deals (indices 3,17,29,41,53,67,79,91), BEN at 16 averaged 31.84 seconds versus v5 at 256 at 41.78 seconds. Linear scaling puts 192 layouts near 31.3 seconds; use 192 for the full rematch and report the actual achieved ratio. Pilot IMP outcomes were not used to choose effort.

## Corrected ACE pilot

The first ACE pilots used the first API evaluation, incorrectly assuming the returned list was best-first. Their strength results are INVALID and retained only for audit. `runs/ace-v5_192-ranked-pilot` is the first valid pilot: four paired boards, v5 -3 IMPs, v5 25.58 seconds/pair, ACE 44.34 seconds/pair (1.73x), median 1,140.5 iterations per nonforced ACE decision. The full ACE run uses the corrected ranking and the same 1s/4s budgets.
