# boxctl: timeout=120
# loop session: read-only. How the arena's collector made its records (audit budget, fork kinds), from the records' own headers.
set -uo pipefail
W=$HOME/work/loop
ls $W/r4arena/*.txt | xargs -n1 basename | sed 's/-feed.txt//' | tr '\n' ' '; echo
python3 - "$W" <<'PY'
import gzip, json, glob, sys, os, collections
W = sys.argv[1]
files = sorted(glob.glob(W + '/r4arena/eps/*.json.gz'))
seen = collections.Counter(); shown = set()
for f in files[::97]:
    try: d = json.load(gzip.open(f, 'rt'))
    except Exception: continue
    if not isinstance(d, dict): continue
    key = (d.get('candidate'), d.get('opponent'))
    seen[key] += 1
    if key in shown or len(shown) >= 4: continue
    shown.add(key)
    print('==', os.path.basename(f)[:70], key)
    print('  schema', d.get('schema'), '| regimes', json.dumps(d.get('regimes'))[:300])
    print('  manifest_identity', json.dumps(d.get('manifest_identity'))[:400])
    print('  versions', json.dumps(d.get('versions'))[:300])
    e = next(iter(d['unique_tables'].values()))
    print('  entry: budget_skips', json.dumps(e.get('budget_skips'))[:200], '| compute', json.dumps(e.get('compute'))[:300], '| audits', len(e.get('audits') or ()), json.dumps((e.get('audits') or [None])[0])[:400])
    for t in e['tables'][:40]:
        if t.get('fork_kind') == 'gap':
            print('  a gap fork table:', {k: (v if k != 'actions' else len(v)) for k, v in t.items()}); break
print(seen.most_common(12))
PY
