# boxctl: timeout=1700
# boxctl: timeout=1700
# g8 (azure6): Max said go on Gen 8 at 15:32 UTC and this box goes to the Gen 8 arena. First my test matches stop (the
# queue's last match, c1, is given up; its rows so far are published). Then the preflight of the opened plans at the
# commit that opened them, with nothing else running: prepare with the families policy v4.1 was trained on left out
# (p41's published list), and six deals played and validated. Under ~/work/g8 only: no collector, feed or publisher.
set -uo pipefail
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
SHA=792c4cb3f647ec71273f0cc57d95be1d0a0a5954; D=$G/src-dry
sudo systemctl stop g8-queue 2>/dev/null; pkill -u "$(id -un)" -f gen8_match.py 2>/dev/null; sleep 3
echo "match queue: $(systemctl is-active g8-queue); c1 rows: $(wc -l < "$G/runs/c1-8c-v-7s/results.jsonl" 2>/dev/null); load: $(cut -d' ' -f1-3 /proc/loadavg)"
[ -d "$D/.git" ] || { git init -q "$D"; git -C "$D" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; }
git -C "$D" fetch -q --depth 1 origin "$SHA" && git -C "$D" checkout -q FETCH_HEAD || { echo "could not check out $SHA"; exit 1; }
cd "$D" || exit 1
for r in models/cardplay/gen7-policy-*/restore*.py models/cardplay/gen8-system-scorer-*/restore*.py; do (cd "$(dirname "$r")" && "$PY" "$(basename "$r")" >/dev/null 2>&1); done
cp "$G/src/bridge_harness/libbridge_dds.so" bridge_harness/ || exit 1
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-families-20261112 || { echo "could not fetch the family list"; exit 1; }
git show FETCH_HEAD:v41_training_families.txt.gz | gunzip | "$PY" -c "
import json, sys
rows = sorted({l.strip() for l in sys.stdin if l.strip()})
json.dump(rows, open(sys.argv[1], 'w')); print('training families in the list:', len(rows))" "$G/v41-training-families.json"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3 BRIDGE_DDS_CACHE=
rm -rf "$G/runs/cand-dry3" "$G/runs/cand-dry3-smoke" "$G/runs/cand-ben-dry3" "$G/runs/cand-bare3"
echo "== the open plans without a list are refused"
"$PY" ops/prepare_gen7_alpha.py --source "$CAP" --run "$G/runs/cand-bare3" --plan configs/round8-candidate.json --shard 63/64 2>&1 | tail -1 | cut -c1-200
[ -e "$G/runs/cand-bare3" ] && { echo "a run was prepared without the list"; exit 1; }
echo "== prepare ($(git log -1 --format=%h)), families left out"
"$PY" ops/prepare_gen7_alpha.py --source "$CAP" --run "$G/runs/cand-dry3" --plan configs/round8-candidate.json --shard 63/64 --exclude-families "$G/v41-training-families.json" 2>&1 | tail -1 | cut -c1-200
"$PY" ops/prepare_gen7_alpha.py --source "$CAP" --run "$G/runs/cand-ben-dry3" --plan configs/round8-candidate-ben.json --shard 62/64 --exclude-families "$G/v41-training-families.json" 2>&1 | tail -1 | cut -c1-160
for run in cand-dry3 cand-ben-dry3; do "$PY" - "$G/runs/$run/manifest.json" <<'PY'
import json, sys, os
if not os.path.exists(sys.argv[1]):
    print('NOT PREPARED:', sys.argv[1]); sys.exit(0)
m = json.load(open(sys.argv[1]))
print(os.path.basename(os.path.dirname(sys.argv[1])), '| cohort', m['identity'][:12], '| deals', m['target'], '| pairs', m['pair_weights'], '| exclusions', {k: (v[:12] if k == 'sha256' else v) for k, v in m['evaluation_exclusions'].items() if k in ('sha256', 'families')})
print('   ', {k: m['bots'][k]['identity'][:12] for k in m['roster']})
PY
done
[ -e "$G/runs/cand-dry3/manifest.json" ] || exit 1
echo "== play (six deals, nothing else on the box)"
start=$(date +%s)
"$PY" ops/smoke_gen7.py --run "$G/runs/cand-dry3" --out "$G/runs/cand-dry3-smoke" --deals 6 > "$G/preflight3.log" 2>&1; code=$?
echo "smoke exit $code in $(( $(date +%s) - start ))s"
[ $code = 0 ] || { grep -v -E "absl|oneDNN|cpu_feature|AVX|^WARNING" "$G/preflight3.log" | tail -14 | cut -c1-300; exit 1; }
"$PY" - "$G/runs/cand-dry3-smoke" <<'PY'
import json, sys
r = json.load(open(sys.argv[1])); t = r['tree']
for d in r['deals']:
    print(f"   deal {d['index']} {d['pair']}: {round(d['seconds'])}s, tables {d['tables']}, IMPs {d['imps']}, searched decisions {d['decisions']}, tree consulted {d['consulted']}, moved {d['moved']}, gap forks {d.get('gap_forks')}")
print('   tree in all:', {k: (round(v, 2) if isinstance(v, float) else v) for k, v in t.items()})
PY
