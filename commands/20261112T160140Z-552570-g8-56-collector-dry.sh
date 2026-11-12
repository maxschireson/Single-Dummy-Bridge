# boxctl: timeout=1500
# boxctl: timeout=1500
# g8 (azure6): a dry trial of the collector and the feed exporter on Gen 8 records, which no preflight covers: the real
# runtime (ops/gen5_runtime.py, eight workers) plays boards of the dry cohort prepared by the previous command, into its
# own folder under ~/work/g8, is stopped cleanly, and the exporter builds its views into another folder there.
# Nothing is published or pushed; no feed exists for it.
set -uo pipefail
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; D=$G/src-dry; RUN=$G/runs/cand-dry3; OUT=$G/runs/cand-dry3-export
[ -e "$RUN/manifest.json" ] || { echo "the dry cohort was not prepared"; exit 1; }
cd "$D" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 TF_CPP_MIN_LOG_LEVEL=3
rm -rf "$OUT"; rm -f "$RUN/STOP"
start=$(date +%s)
nohup "$PY" -u ops/gen5_runtime.py --run "$RUN" --workers 8 > "$G/collector-dry.log" 2>&1 &
pid=$!
boards() { ls "$RUN/receipts" 2>/dev/null | wc -l; }
while [ "$(boards)" -lt 18 ] && [ $(( $(date +%s) - start )) -lt 780 ] && kill -0 $pid 2>/dev/null; do sleep 10; done
touch "$RUN/STOP"
for i in $(seq 1 60); do kill -0 $pid 2>/dev/null || break; sleep 10; done
kill -0 $pid 2>/dev/null && { echo "the collector did not stop in ten minutes; killing it"; kill $pid; }
echo "collector: $(boards) boards in $(( $(date +%s) - start ))s; failures: $(ls "$RUN/failures" 2>/dev/null | tr '\n' ' ')"
[ -z "$(ls "$RUN/failures" 2>/dev/null)" ] || { for f in "$RUN"/failures/*.json; do cut -c1-700 "$f"; echo; done; }
grep -v -E "absl|oneDNN|cpu_feature|AVX|^WARNING" "$G/collector-dry.log" | tail -4 | cut -c1-250
"$PY" - "$RUN" "$OUT" <<'PY'
import glob, gzip, json, sys, collections
from pathlib import Path
sys.path.insert(0, '.')
run, out = Path(sys.argv[1]), Path(sys.argv[2])
rs = [json.load(open(p)) for p in glob.glob(str(run / 'receipts/*.json'))]
by = collections.defaultdict(list)
for r in rs: by[r['pair']].append(r)
for pair, rows in sorted(by.items()):
    print(f"   {pair}: {len(rows)} boards, common IMPs {[r['imps'] for r in rows]}, own {[r.get('own_imps') for r in rows]}, tables {[r['tables'] for r in rows]}")
sources = collections.Counter()
for p in glob.glob(str(run / 'episodes/*.json.gz')):
    d = json.load(gzip.open(p, 'rt'))
    for t in d['unique_tables'].values():
        sources[t['board'].get('auction_source')] += 1
print('   auction sources of the tables played:', dict(sources))
from ops.export_gen5 import export
out.mkdir(parents=True)
try:
    export(run, out)
    d = json.loads((out / 'arena/data.json').read_text())
    print('export: completed', d.get('completed'), '| top keys', sorted(d)[:14])
    labels = d.get('labels') or json.loads((out / 'arena/manifest.json').read_text()).get('labels')
    print('   labels:', {k: labels[k] for k in ('8s-32', '8c-32', '71s-32', '5RZ32', '1') if labels and k in labels})
    print('   files:', sorted(str(p.relative_to(out)) for p in out.rglob('*') if p.is_file())[:6], '...')
except Exception as e:
    import traceback; traceback.print_exc(); print('EXPORT FAILED:', type(e).__name__, str(e)[:300])
PY
