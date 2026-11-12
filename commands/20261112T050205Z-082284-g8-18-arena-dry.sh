# boxctl: timeout=2400
# boxctl: timeout=2400
# g8: dry run of the arena path with a Gen 8 bot, on this box's own capsule clone and under ~/work/g8 only. It checks
# that the Gen 7 preparation step accepts a plan whose bot has the Gen 8 settings and that the preflight plays and
# accepts its records. Nothing is launched: no collector, no feed, no publisher. Two low-priority cores for a few minutes.
set -uo pipefail
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
SHA=ce28246673ec0a802e396fca1fbecf20770210ff; D=$G/src-dry
[ -d "$D/.git" ] || { git init -q "$D"; git -C "$D" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; }
git -C "$D" fetch -q --depth 1 origin "$SHA" && git -C "$D" checkout -q FETCH_HEAD || { echo "could not check out $SHA"; exit 1; }
cd "$D" || exit 1
for r in models/cardplay/gen7-policy-*/restore*.py; do (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>&1); done
cp "$G/src/bridge_harness/libbridge_dds.so" bridge_harness/ || exit 1
cat > "$G/gen8-dryrun-plan.json" <<'PLAN_EOF'
{
 "schema": "gen7-alpha-plan-v1",
 "campaign": "gen8-dryrun-local",
 "title": "Gen 8 prototype: local dry run of the arena path (not a launch)",
 "launch_enabled": true,
 "pending": [],
 "notes": [
  "Authorized by Max, 12 November 2026, 02:09 and 02:16 UTC: launch Gen 7 in the arena with the mix as discussed; the standard bot's tree is margin 0.25, trust 0.3, `path` 0.5, 3 tricks. docs/gen7_candidate_2026-11-11.md is the notice this file belongs to.",
  "A Gen 7 bot is its Gen 6 base bot (same bidder, lead net, scorer, layouts and sample count) with the gen7 engine and policy v4. docs/gen7_alpha_2026-11-11.md explains every setting.",
  "Audit and capture settings (tie audits, gap forks, room seeds) are carried over from the source run, not set here. BEN boards carry no audits (`ben_audit`). Gen 5 and Gen 1 boards carry the cohort's: there is no per-pair switch.",
  "Stop rule: phase 1 ends when every pair has 2,000 completed boards over all collectors together (10,000 in all). A plan has no per-pair target, so watch `by_pair` in state.json and write STOP.",
  "Machines that prepare from the same source run each pass their own --shard K/N to ops/prepare_gen7_alpha.py, so that no deal is played twice.",
  "This is configs/round7-candidate-phase1.json without its two BEN pairs, for machines with no BEN server. The BEN pairs are configs/round7-candidate-phase1-ben.json.",
  "Every board here is two tables on one deal."
 ],
 "model_note": "Gen 7 standard (7s-32) is Gen 6 fast (6-32: same bidder, lead net, hand-fit scorer, layouts and 32 samples) with the gen7 engine (bridge_harness/gen7.py) and policy net v4: layouts weighted by the play so far from trick 7, exact ties broken by the net, and at tricks 3 to 6 a tree search over the net's likeliest cards that re-values the cards the search rates within 0.25 tricks of its best (trust 0.3, stake rule at 0.5 IMPs, at most 3 tricks, 8 layouts). Settings are in the bot's `gen7` block. Every other bot is unchanged from the source run. docs/gen7_alpha_2026-11-11.md has the details.",
 "interpretation": "Gen 7 phase 1: cross-matched feedback before volume. Standard against Gen 6 fast is the generation comparison; BEN (64), BEN (16), Gen 5 (32) and Gen 1 are anchors. Common and native auctions are separate conditions; identical auctions reuse physical games. Only unplayed source deals are allocated; completed source records are unchanged. Intervals are descriptive and unadjusted for repeated monitoring.",
 "roster": [
  "8x-32",
  "7s-32",
  "6-32"
 ],
 "pair_weights": {
  "8x-32~7s-32": 1,
  "8x-32~6-32": 1
 },
 "common_bidder": "6-32",
 "audit_references": {
  "8x-32": "3",
  "7s-32": "3"
 },
 "artifacts": {
  "gen7_policy": {
   "release": "models/cardplay/gen7-policy-v4-2026-11-11",
   "file": "gen7_policy_v4.npz",
   "restore": "restore.py",
   "sha256": "d6b011937ee9ec534ef957061634d9624c5aad56f4c0827ca6c9207bec65dd13"
  }
 },
 "gen7_bots": {
  "7s-32": {
   "base": "6-32",
   "label": "Gen 7 standard (32)",
   "gen7": {
    "play_weight": 0.5,
    "play_floor": 0.05,
    "play_max_layouts": 1024,
    "play_lead": true,
    "tie_break": "net",
    "search_from_trick": 1,
    "net_sample": false,
    "tree_audit": true,
    "tree": [
     {
      "from_trick": 3,
      "to_trick": 6,
      "root_margin": 0.25,
      "root_cards": 3,
      "trust": 0.3,
      "max_solves": 12000,
      "tricks": 3,
      "breadth": 3,
      "mass": 0.98,
      "layouts": 8,
      "reply": "net",
      "reply_power": 1.0,
      "reply_gap": 99.0,
      "own": "best",
      "own_breadth": 0,
      "reply_layouts": 8,
      "reply_pool": 64,
      "plain": 1,
      "path": 0.5,
      "spread": 0.0,
      "path_solves": 3000
     }
    ]
   }
  },
  "8x-32": {
   "base": "6-32",
   "label": "Gen 8 prototype (32), dry run",
   "gen7": {
    "play_weight": 1.0,
    "play_floor": 0.05,
    "play_max_layouts": 1024,
    "play_lead": true,
    "tie_break": "net",
    "search_from_trick": 1,
    "net_sample": false,
    "tree_audit": true,
    "tree": [
     {
      "from_trick": 3,
      "to_trick": 6,
      "root_margin": 0.25,
      "root_cards": 3,
      "trust": 0.3,
      "max_solves": 12000,
      "tricks": 3,
      "breadth": 3,
      "mass": 0.98,
      "layouts": 8,
      "reply": "net",
      "reply_power": 1.0,
      "reply_gap": 99.0,
      "own": "best",
      "own_breadth": 0,
      "reply_layouts": 8,
      "reply_pool": 64,
      "plain": 1,
      "path": 0.5,
      "spread": 0.0,
      "path_solves": 3000
     }
    ],
    "early_play_weight": 1.0,
    "early_pool": 512,
    "early_min_effective": 8.0,
    "opponent_play_weight": {
     "7s-32": 1.0,
     "7f-32": 1.0,
     "8s-32": 1.0,
     "8p-32": 1.0,
     "8x-32": 1.0,
     "8y-32": 1.0,
     "8n-32": 1.0,
     "6-32": 1.0,
     "5RZ32": 1.0,
     "1": 0.2,
     "t-high": 0.2,
     "t-low": 0.5,
     "t-random": 0.25,
     "*": 0.3
    }
   }
  }
 }
}
PLAN_EOF
rm -rf "$G/runs/arena-dry" "$G/runs/arena-dry-smoke"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
echo "== prepare ($(git log -1 --format=%h))"
nice -n 5 "$PY" ops/prepare_gen7_alpha.py --source "$CAP" --run "$G/runs/arena-dry" --plan "$G/gen8-dryrun-plan.json" --shard 63/64 2>&1 | tail -6 | cut -c1-300
[ -e "$G/runs/arena-dry/manifest.json" ] || { echo "no run was prepared"; exit 1; }
"$PY" - "$G/runs/arena-dry/manifest.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1])); b = m['bots']['8x-32']
print('roster', m['roster'], '| pairs', m.get('pair_weights'), '| deals', m.get('target'))
print('8x-32 engine', b.get('engine'), '| identity', b['identity'][:12], '| gen7 settings:', {k: b['gen7'][k] for k in ('play_weight', 'early_play_weight', 'early_pool', 'early_min_effective', 'opponent_play_weight')})
PY
echo "== preflight"
nice -n 5 "$PY" ops/smoke_gen7.py --run "$G/runs/arena-dry" --out "$G/runs/arena-dry-smoke" --deals 2 2>&1 | tail -14 | cut -c1-300
