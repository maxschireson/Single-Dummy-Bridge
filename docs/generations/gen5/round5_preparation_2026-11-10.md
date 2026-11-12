# V5 round preparation

Historical preparation snapshot, superseded by [the Gen5 launch](gen5_launch_2026-11-10.md). The user subsequently selected BEN at 16 samples and the final allocation recorded there.

The user retired 4 and 4p, retained 4b, and requested BEN with neural-only bidding
and 32 samples for opening lead and play. BEN must face v5 only, in about 10% of
scheduled matches. The remaining v5 upgrades and final actor handoff are pending.
No v5 games have been launched or counted.

`configs/round5.json` is the concrete pending plan. The roster is 5, 4b, 3, 2, 1,
and BEN. Each deterministically shuffled 160-deal block has 16 v5–BEN pairs.
The other 144 pairs follow an 8:4:2:1:1 weighting of 5–5, 5–4b, 5–3, 5–2, 5–1.
The denominator includes self-play; the final partial block is approximate.
`bridge_harness/round5.py` rejects any roster containing 4/4p, any other BEN
opponent, and a BEN allocation inconsistent with the declared fraction. Its
launch guard blocks the pending handoff. BEN has a one-match concurrency limit
in the plan so a future dispatcher can keep the slow opponent in its own lane.

The recovered old run is intentionally stopped at 4,869 completed records.
`STOP` and `retirement.json` are in `/workspace/work/gen4-hybrid-mix`.
The public backup on `arena-recovery-feed` also includes STOP and the pending
plan, preventing an archive recovery from accidentally resuming retired bots.
The last published score snapshot contains 4,856 records. It is retained as
published, with complete local games preserved separately; no frozen manifest
or historical outcome was rewritten. Other environments' collectors are not
controlled by this environment.

## BEN configuration and checks

Source: `lorserker/ben` at
`9b5f43104aeac713a80b73513f2f2d6daf9f8769`, the previously calibrated BEN API.
The local checkout is `/workspace/work/ben-next-round` and Python is
`/workspace/work/ben-venv/bin/python`. No model weights were changed or copied
into this repository. Their hashes and the config hash are recorded in
`configs/ben-round5-32.provenance.json`.

`ops/prepare_ben_round5.py` generates the profile from BEN's own API config,
verifies the source commit and model files, and refuses to overwrite a different
profile. The checked-in `configs/ben-round5-32.conf` sets:

- Bidding search threshold −1, no final-contract rescue, no bidding samples when
  search is disabled, and no BBA.
- Opening-lead retained samples 32; cardplay target, minimum and bad-sample
  minimum 32. Neural-only cardplay is disabled, so search is used.
- The review payload limit is also 32, exposing the complete retained sample
  count for verification instead of BEN's default 20 displayed samples.
- Native BEN DDS with one thread; Windows BGA PIMC, ACE and SuitC disabled.
- One concurrent BEN match and a 600-second request timeout in the round plan.

All 17 models and DDS 3.1.0 loaded successfully. A real API preflight reported
`who=NN` with zero bidding samples, then **32 returned samples** for an opening
lead and **32 returned samples** for a later play. Both cards were legal. These
are setup checks, not arena matches or strength evidence. Forced moves and
endings with fewer possible worlds may use fewer than the sample target.

The prepared BEN server listens locally on `127.0.0.1:8087`; its process/log and
preflight results are under `/workspace/work/round5`. The runtime package list is
`configs/ben-round5-runtime-requirements.txt`. The older pinned psutil 5.9 build
attempt required a missing compiler alias; the verified environment uses a
current compatible psutil wheel, with the exact version in that package list.

Example server restart (check the existing listener first):

```sh
cd /workspace/work/ben-next-round
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 \
TF_NUM_INTEROP_THREADS=1 XDG_CACHE_HOME=/workspace/work/ben-cache \
/workspace/work/ben-venv/bin/python src/gameapi.py \
  --config /workspace/Single-Dummy-Bridge/configs/ben-round5-32.conf \
  --host 127.0.0.1 --port 8087 --record false
```

`Round5BenPlayer` wraps the existing HTTP adapter, adds explicit configured
sample-budget metadata and an arena-compatible lifecycle. It supports bidding,
lead and play, skips forced moves and checks card legality. The
final v5 actor factory, bidder, fresh corpus/exclusions and launch identity must
be supplied before attaching it to the next collector. Do not silently replace
the pending v5 actor with a historical model.

## Decision timing

`bridge_harness/decision_timing.py` sums elapsed wall seconds for actual root-game
card decisions and reports decision-weighted means per bot, with opening lead
and later play separately. Forced calls are included; audit continuations,
replayed prefixes, counterfactual forced actions and fixed leads are excluded.
Missing timing is recorded as missing, not zero. The chosen partnership follows
the decision controller, including declarer-controlled dummy moves.

The old recovered feed now has exact timing for its 4,856 published records.
`ops/export_decision_timing.py` uses the actual published replay IDs, rather than
assuming a timestamp cutoff identifies every committed record: a game can have
an earlier completion timestamp but finish validation after a publisher's scan.
The score and replay snapshot remains unchanged.

The shared dashboard displays per-bot timing for selected streams. Existing
streams without timing are marked unavailable. Means combine sums and counts,
not averages of averages, and depend on the host/interface. Repeated played
observations contribute to measured compute time; strength evidence retains
the existing family/matchup deduplication rules.

The next collector should call `from_record` (or `from_game` with an explicit
actor-to-bot map) when committing each family, then publish `decision_timing`
with its score snapshot. BEN timing is measured around the same HTTP adapter
call as other players' `choose` calls; its setup-check times are not mixed into
the dashboard's played-game averages.

Validation: roster/allocation and pending-launch tests, timing exclusion and
weighted-mean tests, the 11 existing dashboard rollup checks, and real BEN lead/
play/net-bidding requests. Browser checks cover the displayed timing table.
