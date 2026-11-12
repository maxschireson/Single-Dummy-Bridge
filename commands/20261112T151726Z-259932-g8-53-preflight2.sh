# boxctl: timeout=2400
# boxctl: timeout=2400
# g8 (azure6): preflight of the Gen 8 candidate on the arena path, again, at the commit that widens the mix (Gen 5,
# Gen 1) and adds the BEN lane; under ~/work/g8 only. A copy of the candidate plan is
# opened for this dry run (the plan in the repository stays closed); ops/prepare_gen7_alpha.py prepares one shard of a
# cohort from this box's capsule clone and ops/smoke_gen7.py plays two deals and validates the records.
# Nothing is launched: no collector, no feed, no publisher.
set -uo pipefail
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
SHA=478e937cc6a5278ef0bac2aa1501b228adf2edb4; D=$G/src-dry
[ -d "$D/.git" ] || { git init -q "$D"; git -C "$D" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; }
git -C "$D" fetch -q --depth 1 origin "$SHA" && git -C "$D" checkout -q FETCH_HEAD || { echo "could not check out $SHA"; exit 1; }
cd "$D" || exit 1
for r in models/cardplay/gen7-policy-*/restore*.py models/cardplay/gen8-system-scorer-*/restore*.py; do (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>&1); done
ls -la models/cardplay/gen8-system-scorer-v1-2026-11-12/*.npz 2>/dev/null | awk '{print $5, $9}'
cp "$G/src/bridge_harness/libbridge_dds.so" bridge_harness/ || exit 1
"$PY" - "$G/gen8-candidate-dry.json" <<'PY'
import json, sys
p = json.load(open('configs/round8-candidate.json'))
assert p['launch_enabled'] is False
p.update(launch_enabled=True, pending=[], campaign='gen8-candidate-dry')
json.dump(p, open(sys.argv[1], 'w'), indent=1)
PY
rm -rf "$G/runs/cand-dry" "$G/runs/cand-dry-smoke" "$G/runs/cand-ben-dry" "$G/runs/cand-closed"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 BRIDGE_DDS_CACHE=
echo "== the closed plan is refused"
nice -n 5 "$PY" ops/prepare_gen7_alpha.py --source "$CAP" --run "$G/runs/cand-closed" --plan configs/round8-candidate.json --shard 63/64 2>&1 | tail -1 | cut -c1-200
echo "== prepare ($(git log -1 --format=%h))"
nice -n 5 "$PY" ops/prepare_gen7_alpha.py --source "$CAP" --run "$G/runs/cand-dry" --plan "$G/gen8-candidate-dry.json" --shard 63/64 2>&1 | tail -6 | cut -c1-300
[ -e "$G/runs/cand-dry/manifest.json" ] || { echo "no run was prepared"; exit 1; }
"$PY" - "$G/runs/cand-dry/manifest.json" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
print('roster', m['roster'], '| pairs', m.get('pair_weights'), '| deals', m.get('target'))
print('systems', m.get('systems'))
print('gen8', json.dumps(m.get('gen8'))[:400])
for k in m['roster']:
    b = m['bots'][k]
    print(k, 'engine', b.get('engine'), '| identity', b['identity'][:12], '| bidder', (b.get('bidder') or {}).get('sha256', '-')[:12], '| lead_systems', b.get('lead_systems'))
PY
echo "== the BEN lane: prepare only (a BEN board needs BEN's server)"
"$PY" - "$G/gen8-candidate-ben-dry.json" <<'PY'
import json, sys
p = json.load(open('configs/round8-candidate-ben.json'))
assert p['launch_enabled'] is False
p.update(launch_enabled=True, pending=[], campaign='gen8-candidate-ben-dry')
json.dump(p, open(sys.argv[1], 'w'), indent=1)
PY
nice -n 5 "$PY" ops/prepare_gen7_alpha.py --source "$CAP" --run "$G/runs/cand-ben-dry" --plan "$G/gen8-candidate-ben-dry.json" --shard 62/64 2>&1 | tail -1 | cut -c1-260
"$PY" - "$G/runs/cand-ben-dry/manifest.json" <<'PY'
import json, sys, os
if not os.path.exists(sys.argv[1]):
    print('no BEN run was prepared'); sys.exit(0)
m = json.load(open(sys.argv[1]))
print('BEN lane roster', m['roster'], '| pairs', m.get('pair_weights'), '| deals', m.get('target'), '| systems', m.get('systems'))
print('BEN lane 8s-32 identity', m['bots']['8s-32']['identity'][:12])
PY
echo "== preflight"
nice -n 5 "$PY" ops/smoke_gen7.py --run "$G/runs/cand-dry" --out "$G/runs/cand-dry-smoke" --deals 6 2>&1 | grep -v "^WARNING\|tensorflow/\|oneDNN\|cpu_feature" | tail -16 | cut -c1-400
"$PY" - "$G/runs/cand-dry-smoke" <<'PY'
import json, sys, os
p = sys.argv[1]
if os.path.isdir(p):
    print('smoke folder:', sorted(os.listdir(p))[:10])
else:
    r = json.load(open(p))
    for k, v in r.items():
        s = json.dumps(v); print(k, ':', s if len(s) < 1500 else s[:1500] + '...')
PY
