# Gen 6: new play architecture — how it fits together, and how to launch it

> Historical launch-design snapshot. Gen6 has since launched. For the adopted fast/medium profiles, BEN allocation and deployment status sources, read [current system](../../current-system.md) and [recovery](gen6-arena-recovery-20261111.md). The algorithms below remain useful; the initial status and defaults are not the current deployment plan.

Status, 11 November 2026: engine, tests, launch files and the three model releases are on this
branch. `configs/round6.json` is closed (`launch_enabled: false`) until Max's match mix is put
in. No arena match has been played with this engine; the evidence below is offline.

Base: `codex/launch-gen5rz-ben-20261110` (4969fc2). Every existing file is unchanged except three
added lines in `ops/gen5_runtime.py` (the engine dispatch).

## What a Gen 6 bot is

| Part | Gen 5RZ (32) | Gen 6 (32) |
| --- | --- | --- |
| Bidder | Gen5 (`play50_anchor002`) | Gen 6 candidate, graded alternatives |
| Layouts, opening lead | belief sampler, pool of 128 reduced to at most 32 | 32 from the lead belief net |
| Layouts, tricks 1–5 | same sampler; pool reduced while 10+ tricks remain, then 32 draws | hand-type classes weighted by the hand-fit scorer: 32 at tricks 1–2, 64 at tricks 3–5 |
| Layouts, tricks 6–13 | 32 draws from the sampler | deal list: every layout that fits the cards, weighted by the scorer; up to 256 solved |
| Card choice | DDS mean tricks; policy net among exact ties | same |
| Policy net | Gen5 policy | same file, same rule (`near_tie` 0) |

"Belief sampler" is the Gen5 per-card belief net. It stays in the spec only so that a phase can
be switched back to it.

## One decision

1. **Which layouts.**
   - *Opening lead.* The lead belief net samples the declarer's and dummy's hands as tokens
     (shape, then honours per suit); partner gets the rest; spot cards are dealt at random. It
     was trained from the leader's seat only. Auctions of more than 25 calls do not fit its
     28-slot window and fall back to the scorer on a weighted pool of uniform layouts.
   - *After dummy appears, until the deal list starts.* The bidder and both nets see a hand as
     A, K, Q, J, T per suit plus a count of low cards. Layouts that give a hidden hand the same
     honours and the same number of low cards per suit are one class. Every class is listed
     (10k–260k at trick 1), weighted by its number of layouts times the scorer's value for both
     hidden hands' original thirteen cards, and layouts are dealt from classes spaced evenly
     through the cumulative weight. This is the exact scorer-weighted posterior at any trick.
   - *From `list_from_trick` (6).* Every layout that fits the cards and show-outs is listed (at
     most 12,870 at the start of trick 6) and weighted the same way. If the list is longer than
     `list_solve`, that many are drawn in proportion to weight; otherwise all are solved with
     their weights.
2. **DDS.** Each distinct layout is solved once. Cards are ranked by weighted mean tricks.
3. **Policy.** Cards within `near_tie` (0) of the best are eligible. With one eligible card the
   policy net is not consulted. With several it picks among them, by the same code path as
   `ArenaPlayer` (a test compares the two). The policy net is told a sample count clamped to
   32–192, the range it was trained on.

No bidder is asked about a hidden hand during play. The lead net takes the frozen Gen5 bidder's
recurrent features for the leader's own hand as one of its inputs; that is the only bidder
computation at the table after the auction.

## Models

| Role | Release folder | File | SHA-256 | Trained on |
| --- | --- | --- | --- | --- |
| Bidder | `models/bidding/gen6-candidate-2026-11-11` | `bidder.keras` | `5b7ea255…95e7ff` | Gen5 parent plus graded alternatives |
| Lead belief net | `models/cardplay/joint-auction-belief-lead-v0-2026-11-10` | `joint_lead_v0.npz` | `72fc7c3e…9e6291` | 2.2M deals bid by the Gen5 bidder |
| Hand-fit scorer v0 | `models/cardplay/hand-fit-scorer-v0-2026-11-11` | `hand_fit_v0.npz` | `56e64440…245e73` | 230,010 deals bid by the Gen5 bidder |
| Lead net's bidder features | the source run's `artifacts/v5/bidder.keras` | | `9ee52f3b…014dcc` | (Gen5 bidder) |
| Policy, Gen5 belief | the source run's Gen5 files | | unchanged | |

Full hashes are in `configs/round6.json`. Each release folder has a restore script that rebuilds
the file from its parts and checks it; `ops/prepare_gen6.py` runs it when the file is missing.

Both play nets were trained on Gen5-bidder auctions. The lead net and the scorer release folders
were copied unchanged from `research/joint-auction-belief-20261110` (2b81ced); their READMEs call
them research prototypes, and this document is where their use in Gen 6 is defined.

## Switches

`samples` and `near_tie` are ordinary spec keys. The rest live in `spec['gen6']`; `prepare`
writes every value into the bot spec, so the bot identity pins them.

| Switch | Default | Meaning |
| --- | --- | --- |
| `samples` | 32 | layouts at the opening lead and at tricks before `mid_from_trick` |
| `mid_from_trick` | 3 | from this trick until the deal list starts, deal `mid_samples` layouts |
| `mid_samples` | 64 | see above |
| `list_from_trick` | 6 | first trick decided from the deal list; 14 = never |
| `list_solve` | 256 | most layouts solved from the list; 0 = the whole list |
| `list_max_layouts` | 20000 | a longer list is not built; that decision uses the class method |
| `early_pick` | `spaced` | `spaced` = evenly through the cumulative class weight; `random` = independent draws; `strata` = one random member per cluster of `cluster_pool` independent draws, weighted by cluster size; `centres` = each cluster's centre |
| `cluster_pool` | 256 | draws clustered by `strata` and `centres`; only the picks are solved |
| `lead_source` | `lead_net` | `lead_net`, `scorer` (weighted pool of `lead_pool` uniform layouts) or `gen5` |
| `early_source` | `scorer` | `scorer` or `gen5`, for decisions after the lead and before the deal list |
| `leader_early_source` | `` | `lead_net` = the opening leader's own tricks before the list use the lead net's probability of (declarer's hand, the actual dummy) as the class weight |
| `lead_pool` | 32768 | pool size when the scorer has to make the opening lead |
| `near_tie` | 0 | policy window in tricks; 0 = exact ties only |

`gen5` means the unchanged Gen5R/RZ decision for that phase (the spec's belief net, sample count
and layout reduction). With `lead_source` and `early_source` at `gen5` and `list_from_trick` 14 a
Gen 6 bot plays card for card like its base bot; a test checks this.

`configs/round6.json` lists three ready-made variants for ablation (`gen6_variants_for_ablation`):
Gen5 beliefs in tricks 1–5, no deal list, and lead-net weights for the leader's tricks 1–5.

## Launch

```bash
# 1. Put the match mix into configs/round6.json: roster, pair_weights, common_bidder,
#    audit_references. Empty `pending`, set launch_enabled to true.
# 2. Drain the current collector (STOP and WATCHDOG_STOP present), then freeze the Gen6 cohort:
python ops/prepare_gen6.py --source /workspace/work/<current-run> --run /workspace/work/gen6
# 3. Preflight through the real runtime path (bidding, both auction conditions, swapped rooms,
#    audit forks, replay, record validation). Writes nothing into the run:
python ops/smoke_gen6.py --run /workspace/work/gen6 --out reports/gen6-preflight.json --deals 4
#    Each row reports native_auction_differs per room. If no deal has a native auction that
#    differs from the common one, run more deals or use --start to reach one.
# 4. Start as before:
python ops/gen5_runtime.py --run /workspace/work/gen6 --workers 3
```

- `prepare_gen6.py` follows `prepare_gen5rz_ben.py`: unplayed source deals only, source bots
  copied unchanged, Gen6 bots built from their base bot's spec (`5RZ32`), artifacts copied and
  hash-checked. It checks the source by manifest, bot identities, artifacts and corpus. It does
  not compare the source's pinned code hash, because the engine adds files under `bridge_harness/`.
- The new run pins the new code hash. A Gen5 run cannot be resumed from this checkout; keep its
  own checkout for that.
- `common_bidder` decides which auctions the common condition is played on. `5RZ32` keeps it on
  Gen5 auctions, which both play nets were trained on. A Gen6 bot there moves it to the graded
  bidder's auctions.
- `ops/export_gen5.py` branches on `variant` in ('5R', '5RZ'); the manifest here has variant
  `6`. The report side was not touched.
- Needs `h5py` at run time (already a Keras dependency) to read the Gen5 bidder's weights for
  the lead net's input.

## Evidence

Measured, all offline, double-dummy scored, on recorded Gen5 common-auction tables unless stated:

| What | Result | Source |
| --- | --- | --- |
| Lead net vs Gen5 belief sampler, 32 layouts each | +0.033 ± 0.006 tricks, +0.11 ± 0.02 IMPs per lead (190 leads); equal to exact auction-posterior layouts | `reports/auction_belief_lead_2026-11-10.md` on the research branch |
| Lead net on graded-bidder auctions | 6.10 ± 0.02 nats over uniform against 6.18 ± 0.02 on Gen5 auctions (16,384 deals); exact layouts beat the net's by +0.002 ± 0.010 tricks per lead there against +0.015 ± 0.008 on Gen5 auctions (54 leads each) | cross-inference test, 10 Nov, Gen6 package chat (records not pushed) |
| Scorer-weighted deal list vs Gen5 sampler, tricks 6–12 | +0.106 ± 0.028 tricks, +0.27 ± 0.11 IMPs per table (400 tables, 9,426 decisions); bidder-built lists are +0.025 ± 0.017 above the scorer | belief-research chat, 11 Nov; its play report is not on GitHub yet |
| Bidding information held in late play | Gen5 sampler 0.36, scorer 1.11, bidder list 1.39 nats per decision | same |
| Same measure through this engine's code | scorer holds 78% of the bidder list's information (30 tables, 210 decisions), against 79–81% reported there | this package |
| Scorer on classes vs Gen5 sampler, whole play, 32 layouts each | +0.23 ± 0.09 tricks per table, tricks 1–5 alone +0.18 ± 0.08 (first 60 of 200 tables) | belief-research chat, interim |
| Layout choice in tricks 1–5 | table below | this package's chat, running the research branch's test |
| Policy on exact ties only | 5RZ32 vs 5R32 +0.23 ± 0.08 IMPs/board (1,759 arena boards) | policy-threshold chat, 11 Nov |
| Bidder vs Gen5 bidder | +0.331 ± 0.068 IMPs/board, double-dummy duplicate on 2,270 solved deals | `models/bidding/gen6-candidate-2026-11-11` |

Layout choice in tricks 1–5 (109 tables, 1,841 decisions; expected double-dummy loss in tricks
per table against 256 held-out posterior layouts; scorer = a 7-minute copy, not v0; records and
method in `reports/gen6-layout-selection-2026-11-11/`):

| Layouts solved | Loss | Against 32 independent draws |
| --- | --- | --- |
| 32 independent draws | 0.073 | |
| 32 evenly spaced | 0.039 | +0.035 ± 0.011 |
| 32 cluster centres | 0.047 | +0.026 ± 0.011 |
| 32, one random member per cluster | 0.050 | +0.024 ± 0.011 |
| 32 most likely classes | 0.151 | −0.078 ± 0.016 |
| 64 independent draws | 0.030 | +0.043 ± 0.011 |
| 128 independent draws | 0.017 | +0.056 ± 0.011 |
| 256 independent draws | 0.009 | +0.064 ± 0.011 |

Evenly spaced picks at 64 (39 of the tables): loss 0.019, level with 128 independent draws
(128 is +0.002 ± 0.006 better), +0.020 ± 0.008 better than 64 independent draws and
+0.003 ± 0.006 better than 64 cluster centres. Against evenly spaced 32 it gains
+0.005 ± 0.004 in tricks 1–2 and +0.009 ± 0.006 in tricks 3–5. At 32, one per cluster is
0.011 ± 0.006 behind evenly spaced. Hence the defaults: evenly spaced, 32 at tricks 1–2 where a
layout costs about four times as much to solve, 64 at tricks 3–5. `mid_from_trick: 1` gives 64
from trick 1. The cluster picks stay available as switch values.

Port checks (this package): lead net log-likelihoods equal the research code's to 1e-4 nats and
its samples are identical draw for draw on 120 leads; bidder features to 2e-6; scorer scores equal
`fit.log_score` on v0's weights to 8e-6 on 19,680 hands; class weights equal the layout listing's
(unit test).

Not measured:

- The whole bot in the arena. Nothing above is a played match with this engine.
- The scorer after the lead on auctions from any bidder other than Gen5's. In native auctions
  a Gen6 partner bids with the graded bidder (3% of calls differ from Gen5 along Gen5 auctions),
  and bots 4b, 3, 2 and 1 bid with `dds-40000`, BEN with its own net.
- The lead net's weights for the leader's own early tricks (`leader_early_source`, off).
- The policy net's tie-break on weighted layouts. Exact ties are rarer with weighted lists than
  with 32 equal samples, so it is consulted on fewer decisions that matter.
- 64 layouts at tricks 3–5 and 256 from the list as played results; they rest on the
  layout-choice test above and on the research chat's 256-vs-32 late-play comparison
  (+0.014 ± 0.014 for the scorer).

## Time per decision

One idle core, default switches, preflight on a mock run (3 deals, 6 tables, 122 Gen 6
decisions), seconds:

| Phase | Layouts solved | Mean | Max seen |
| --- | --- | --- | --- |
| Opening lead (lead net) | 32 | 0.93 | 1.5 |
| Trick 1 after the lead | 32 | 1.6 | 5.1 |
| Tricks 2–5 | 56 on average | 0.13 | 0.65 |
| Deal list, tricks 6–12 | 119 on average | 0.02 | 0.08 |

Trick 1 is the slow step: each seat's classes are listed and scored once there (pure NumPy);
later decisions of that seat reuse the scores. A deal (two rooms, both bots, audit forks at the
mock run's reduced audit budget) took 4–16 s. That preflight passed its checks: every phase
exercised, no Gen 6 card below the best, 73 policy tie-breaks, records replayed and validated by
`ops/gen5_runtime.validate`. A second preflight on deals where the Gen 6 side's native auction
differs from the common one (3 deals, 9 tables, 180 Gen 6 decisions) passed the same checks, and
so did the first preflight repeated from a clean clone of the pushed branch.

The cluster picks add about 0.02 s per decision in tricks 3–5 and nothing measurable at tricks
1–2 (one board, two rooms).

## Code

- `bridge_harness/gen6.py` — `Gen6Player` (an `ArenaPlayer`), `Gen6Config`, `View` (what is
  unseen, the deal list), `Classes` (hand-type classes, ported from the research branch's
  `classes.py`).
- `bridge_harness/gen6_nets.py` — NumPy inference: `LeadNet`, `FitScorer`, `BidderState`.
- `ops/gen5_runtime.py` — three added lines: specs with `engine: gen6` get `Gen6Player`.
- `ops/prepare_gen6.py`, `ops/smoke_gen6.py`, `configs/round6.json`.
- `tests/test_gen6.py` (17 tests), `tests/test_gen6_launch.py` (5 tests):
  `python -m unittest tests.test_gen6 tests.test_gen6_launch`.

Each Gen6 decision records `gen6` in its action details: source (`lead_net`, `scorer`,
`deal_list`, `gen5`), trick, classes or layouts listed, effective count of the weights, layouts
drawn, seconds for layouts and for DDS, and the settings.
