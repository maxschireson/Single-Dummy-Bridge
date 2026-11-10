# Auction belief at the opening lead: ceiling test and joint-net prototype

10 November 2026. Run in a Claude workspace (2 cores) on the `arena-gen5-codex-32-feed` branch: Gen5 bidder, v5 belief net, the runtime's own solver build. Nothing in the bot was changed.

## Result

All numbers are per opening lead, 32 layouts per arm, double-dummy scored.

| Comparison | Tricks | IMPs |
|---|---:|---:|
| Exact layouts vs v5 belief sampler (191 leads) | +0.033 ± 0.007 | +0.11 ± 0.03 |
| Joint net vs v5 belief sampler (190 leads) | +0.033 ± 0.006 | +0.11 ± 0.02 |
| Exact layouts vs joint net | +0.000 ± 0.005 | −0.00 ± 0.02 |
| Joint net at 32 vs v5 at 128 | +0.015 ± 0.007 | +0.06 ± 0.03 |
| Joint net + bidder filter vs v5 | +0.032 ± 0.006 | +0.10 ± 0.02 |

- A net trained only on free data (random deals bid by the Gen5 bidder) recovers the whole gain that exact auction-posterior layouts give at the lead.
- The bidder used as a final filter adds nothing measurable on top of the net.
- On the true deal alone the net is +0.040 ± 0.020 tricks over v5, the same direction with more noise.

## Why the exact posterior is available

In the common-auction condition every seat bids greedily with one network. A hidden hand is possible exactly when that network, holding it, makes the calls the seat made. Deals are uniform, so the opening leader's posterior is uniform over layouts whose three hidden hands all pass. `exact.py` samples it by rejection; `nbid.py` is a NumPy copy of the bidder.

The true deal is one draw from that posterior. So a lead can be scored on held-out exact layouts instead of the single true deal; the expectation is the same and the standard errors are about 2.7 times smaller here. Both yardsticks are reported.

## Ceiling test (191 leads, episodes 0–199 of the feed)

Layout sets per lead: 64 exact, 128 from the bot's own `WeightedSampler` on v5 logits, 32 uniform. Each set's lead is the one with the best mean double-dummy value, exact ties split evenly.

Exact-32 minus the other arm, held-out exact layouts as yardstick:

| Other arm | Tricks | IMPs | True deal, tricks |
|---|---:|---:|---:|
| v5 belief, 32 | +0.0325 ± 0.0072 | +0.107 ± 0.028 | +0.052 ± 0.020 |
| v5 belief, 64 | +0.0193 ± 0.0071 | +0.076 ± 0.031 | +0.037 ± 0.021 |
| v5 belief, 128 | +0.0154 ± 0.0082 | +0.058 ± 0.034 | +0.027 ± 0.027 |
| uniform, 32 | +0.0645 ± 0.0116 | +0.182 ± 0.038 | +0.065 ± 0.031 |

Other pairs, same yardstick:

| Pair | Tricks | IMPs |
|---|---:|---:|
| v5 32 vs uniform 32 | +0.0320 ± 0.0115 | +0.074 ± 0.037 |
| v5 64 vs v5 32 | +0.0132 ± 0.0032 | +0.031 ± 0.012 |
| v5 128 vs v5 32 | +0.0171 ± 0.0043 | +0.049 ± 0.014 |
| v5 128 vs v5 64 | +0.0039 ± 0.0041 | +0.018 ± 0.013 |

Exact-32 vs v5-32 by subgroup:

| Subgroup | Leads | Tricks | IMPs |
|---|---:|---:|---:|
| Notrump contracts | 45 | +0.082 ± 0.020 | +0.20 ± 0.06 |
| Suit contracts | 146 | +0.017 ± 0.007 | +0.08 ± 0.03 |
| Tighter auctions (above-median sampler work) | 95 | +0.039 ± 0.010 | +0.15 ± 0.05 |
| Looser auctions | 96 | +0.026 ± 0.010 | +0.06 ± 0.03 |
| Capped leads excluded | 186 | +0.033 ± 0.007 | +0.11 ± 0.03 |

Layout quality on the same leads:

| | Uniform | v5 belief | Exact |
|---|---:|---:|---:|
| Layouts consistent with the auction | 0.11% | 1.19% (median 0%) | 100% |
| Summed HCP error of the three hidden hands | 13.9 | 10.4 | 4.0 |
| Summed suit-length error | 17.2 | 15.1 | 8.9 |
| Mean double-dummy cost of the lead on the true deal, 32 layouts | 0.240 ± 0.037 | 0.227 ± 0.029 | 0.175 ± 0.030 |

## Information accounting (nats per layout, relative to uniform)

- Available from the auction, −log of the consistent share: 8.63 ± 0.22 (median 8.1; 10th–90th percentile 5.5–12.7; 144 leads).
- Captured by the v5 sampler, its exact log-probability of the true layout: 1.96 ± 0.16.
- Captured by the joint net on the same leads: 6.29 ± 0.15.
- The consistent share estimated two independent ways (rejection counts; the net's importance weights on layouts that pass) agrees: log share −8.51 vs −8.51, difference −0.005 ± 0.020, correlation 0.996 (141 leads).

## Joint net (prototype, opening leader's view only)

- **Structure the bidder imposes.** The Gen5 bidder sees a hand as A, K, Q, J, T per suit plus a count of lower cards. So the auction posterior is over each hidden hand's shape and honours, and spot cards are exactly uniform given those.
- **Output.** Ten tokens: declarer's shape (one of 560), declarer's honours suit by suit (four tokens of up to 32 options), then the same for dummy. Partner gets the remainder; spots are dealt uniformly. Each token is a masked softmax conditioned on everything placed so far, so the likelihood is exact and no illegal layout can be drawn.
- **Input.** Leader's hand, vulnerability, the auction in 28 seat-aligned slots, and the frozen bidder's final 256-unit state for the leader's seat. Auctions over 25 calls do not fit (0.2% of generated deals; 1 of the 191 test leads).
- **Size.** 1,311,616 parameters, dense layers only.
- **Data.** 2.2M random deals bid by the Gen5 bidder (`gen.py`, seeds 1000 and 1001), 9–10 minutes on two cores. The batched simulator reproduces 300 of 300 recorded auctions and declarers.
- **Training.** 26 minutes on two cores, 6.6M rows (3.0 passes), Adam with cosine decay, NumPy with `autograd`. Fresh-deal likelihood 6.23 ± 0.02 nats over uniform at the end, 5.2 after 4 minutes. Single run, single seed.
- **Pass rate.** 31.7% of its layouts pass the bidder (median 31.1%); zero of 256 on 5% of leads. With the bidder as filter, 32 passing layouts were found within 8,192 proposals on 95% of leads.
- **Reweighting.** Importance weights that would turn passing layouts into exact posterior draws have an effective sample share of 36% (median).

## Later play: what is known without using card choices

119 recorded common-auction deals, each seat's first decision in tricks 2, 4, 6, 8 and 10 (1,785 positions). Nats per position.

- **Cards**: log count of layouts consistent with the cards seen and show-outs (exact).
- **Auction**: further reduction when each hidden seat's original 13 cards (held plus already played) must pass the bidder test. Exact by full enumeration up to 16,000 layouts, otherwise from 4,000 uniform samples.
- **v5**: v5's exact log-probability of the true layout minus the cards-only log-probability. v5 sees the auction and the whole play.

| Trick | Cards | Auction | v5 | Auction − v5 | Median layouts, cards only | After auction |
|---:|---:|---:|---:|---:|---:|---:|
| 2 | 14.10 | 3.57 ± 0.10 | 0.91 ± 0.07 | 2.66 ± 0.08 | 1,352,078 | 34,478 |
| 4 | 11.12 | 3.19 ± 0.09 | 0.88 ± 0.06 | 2.31 ± 0.07 | 92,378 | 2,656 |
| 6 | 8.21 | 2.56 ± 0.09 | 0.70 ± 0.06 | 1.87 ± 0.06 | 6,435 | 271 |
| 8 | 5.44 | 1.90 ± 0.07 | 0.54 ± 0.05 | 1.36 ± 0.05 | 252 | 30 |
| 10 | 2.80 | 1.07 ± 0.05 | 0.32 ± 0.04 | 0.75 ± 0.04 | 20 | 6 |

- v5 beats the auction-only figure in 2% of positions at trick 2 and 12% at trick 10.
- The auction says more to the defenders than to declarer: at trick 6, 3.0 and 3.1 nats for the two defenders against 1.6 for declarer.
- From about trick 6 the layouts that survive cards and bidding are few enough to list and solve in full (median 271 at trick 6, 30 at trick 8), so belief there can be an exact weighted list instead of a sample.
- Not measured: what the card choices themselves add. That needs a play-likelihood model. v5's column bounds what v5 extracts from auction and choices together.

## Cost

- Exact rejection sampling: median 1.2 s, mean 4.2 s per lead for 64 layouts; 2.6% of leads hit the work cap.
- Solver: about 13 s per lead for 224 layouts with both cores busy (51 ms per layout on an idle core).
- Net sampling: 0.73 s per lead for at least 2,304 proposals including bidder checks, in unoptimised Python.

## Limits and checks not run

- Opening lead only. Double-dummy scoring; the bot's 0.125-trick window and selector are not modelled.
- Common-auction self-play only. Against BEN's or a person's bidding the bidder is a model, not a judge; the net would be trained on their auctions.
- No arena match. At 3.8 IMPs per paired board, resolving +0.05 IMPs/board at two standard errors takes about 23,000 boards.
- Spots uniform is exact for this bidder's input encoding and not for a bidder that sees spot cards.
- Exact sets for tight auctions reuse block hands: 57.8 distinct of 64 on average. The true-deal yardstick, which is unaffected, agrees with the held-out one.
- Regret levels against the held-out best lead are optimistic by the maximum; paired differences are not.
- The joint net is built for the opening leader only. The later-play section measures information, not decisions, and does not model card choices.

## Files

Code and per-lead results are in `analysis/auction_belief/`; the trained net is in `models/cardplay/joint-auction-belief-lead-v0-2026-11-10/` as 512 KiB parts with its log; `python restore.py` there rebuilds `joint_lead_v0.npz`. Nothing under `bridge_harness/` or `scripts/` is changed.

- `nbid.py` NumPy bidder and per-seat consistency test. `verify_bidder.py` checks it on recorded auctions.
- `exact.py` exact posterior sampler. `test_exact.py`, `test_exact2.py` compare it with full enumeration on toy problems.
- `lead_ceiling.py` builds the layout sets and solves them. `analyze_leads.py`, `analyze_leads2.py` report the ceiling.
- `info_nats.py` information accounting at the lead.
- `gen.py` batched auction simulator and training rows. `test_gen.py` checks it on recorded auctions.
- `joint.py`, `train_joint.py` the net and its trainer. `eval_joint.py`, `analyze_model.py` the lead test.
- `play_info.py`, `analyze_play.py` the later-play measurement.
- `out/` results, gzipped: `main_*` ceiling test, `eval_*` net lead test, `play_*` later play, `info.json` per-lead nats.

Set `SDB_FEED` to the feed's `recovery` folder (it holds `artifacts/`, `episodes/`, `runtime/`). Needs NumPy, h5py and autograd. Training data is not stored; `gen.py` regenerates it from the seeds below in about 10 minutes on two cores.

```bash
cd analysis/auction_belief
export SDB_FEED=/path/to/feed/recovery
M=../../models/cardplay/joint-auction-belief-lead-v0-2026-11-10/joint_lead_v0.npz
python verify_bidder.py 100
python analyze_leads2.py && python analyze_model.py && python analyze_play.py    # reproduce the tables from stored results
python lead_ceiling.py out/main_0.jsonl 0 200 2 0 64 128 32     # rerun the ceiling test; offset 1 in a second process
python info_nats.py
python gen.py data/train0.npz 1000 1100000 && python gen.py data/train1.npz 1001 1100000 && python gen.py data/val.npz 5 30000
python train_joint.py weights/joint 30 data/val.npz data/train0.npz data/train1.npz
python eval_joint.py $M out/eval_0.jsonl 2 0 64    # offset 1 in a second process
python play_info.py out/play_0.jsonl 0 120 2 0     # offset 1 in a second process
```
