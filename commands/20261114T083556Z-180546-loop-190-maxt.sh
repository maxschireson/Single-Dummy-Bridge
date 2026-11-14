# boxctl: timeout=60
# boxctl: timeout=60
python3 - <<'PY'
import gzip, json, glob, os, collections
c = collections.Counter()
for f in glob.glob(os.path.expanduser('~/work/loop/pub/usbc/usbc_*.json.gz')):
    d = json.load(gzip.open(f, 'rt'))
    for t in d.get('tables', []):
        full = next((e['payload'] for e in t['events'] if e.get('tt') == 'FULL'), {})
        for s, p in (full.get('ps') or {}).items():
            if 'schireson' in (p.get('name') or '').lower():
                c[(p['name'], d['miniSessionId'], full.get('tname', '')[:40])] += 1
for k, v in sorted(c.items()): print(v, k)
print('total tables seated:', sum(v for k, v in c.items() if k[0].startswith('Max')))
PY
