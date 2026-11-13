# boxctl: timeout=1800
# boxctl: timeout=1800
# x8 session, azure6 (Max, 06:40-06:4x UTC: 8X v3 into the arena, on lanes of g7's arena boxes). Preflight of
# configs/round8x-v3.json (feature/gen8x-arena-20261113 at 6b99997) before asking g7: prepare it from a LOCAL PREFLIGHT
# source (the capsule's bots with 40 generated deals; never an arena source) with the published exclusion list, then
# ops/smoke_gen7.py --deals 1 through the real runtime (TensorFlow bidders). Writes only under ~/work/x8/prep.
set -euo pipefail
COMMIT=6b9999720078fdeffece4dc6adaa27c69b3fcf9c
W=$HOME/work/x8; S3=$W/src3; S4=$W/src4; PY=$HOME/work/venv/bin/python; P=$W/prep
rm -rf "$S4" "$P"; cp -a "$S3" "$S4"; mkdir -p "$P"
git -C "$S4" fetch -q --depth 5 origin feature/gen8x-arena-20261113 && git -C "$S4" checkout -q "$COMMIT"
git -C "$S4" log -1 --format='src4 %h %s' | cut -c1-100
cd "$S4"
(cd models/cardplay/gen8-system-scorer-v1-2026-11-12 && "$PY" restore_model.py | tail -1)
(cd models/cardplay/rollout-net-v1-20261113 && "$PY" restore.py | tail -1)
git fetch -q --depth 1 origin transfer/rollout-net-v1-training-families-20261113
git show FETCH_HEAD:gen8x-v3-exclusions.json > "$P/gen8x-v3-exclusions.json"; sha256sum "$P/gen8x-v3-exclusions.json"
cp -a $HOME/work/capsule-gen7-capture/recovery "$P/source"
"$PY" - "$P/source" <<'PYEOF'
import json, sys
from pathlib import Path
sys.path.insert(0, '.')
from bridge_harness.corpus import generate, save
from bridge_harness.loop_registry import sha
from bridge_harness.training import digest
src = Path(sys.argv[1]); m = json.loads((src / 'manifest.json').read_text())
save(list(generate(40, 777013)), src / 'corpus.jsonl')
m.update(corpus='corpus.jsonl', corpus_sha256=sha(src / 'corpus.jsonl'), target=40,
         title='LOCAL PREFLIGHT SOURCE ONLY (x8 session): capsule bots with 40 generated deals; never an arena source')
m.pop('identity'); m['identity'] = digest(m); (src / 'manifest.json').write_text(json.dumps(m, indent=1)); print('preflight source', m['identity'][:12])
PYEOF
touch "$P/source/STOP" "$P/source/WATCHDOG_STOP"; mkdir -p "$P/source/episodes" "$P/source/receipts" "$P/source/failures"
"$PY" ops/prepare_gen7_alpha.py --source "$P/source" --run "$P/run8x" --plan configs/round8x-v3.json --exclude-families "$P/gen8x-v3-exclusions.json" > "$P/prepare.log" 2>&1; tail -c 300 "$P/prepare.log"; echo
"$PY" -c "import json; m=json.load(open('$P/run8x/manifest.json')); print({k: (v.get('engine'), v['identity'][:12]) for k, v in m['bots'].items() if k in ('8x3-32','8s-32','71s-32','5RZ32','1')})"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE=
start=$(date +%s)
timeout 1500 "$PY" ops/smoke_gen7.py --run "$P/run8x" --out "$P/smoke8x.json" --deals 1 > "$P/smoke.log" 2>&1; echo "smoke exit $? in $(( $(date +%s) - start )) s"
tail -5 "$P/smoke.log" | cut -c1-300
"$PY" -c "import json; r=json.load(open('$P/smoke8x.json')); print(json.dumps(r)[:2500])" 2>&1 | tail -3
