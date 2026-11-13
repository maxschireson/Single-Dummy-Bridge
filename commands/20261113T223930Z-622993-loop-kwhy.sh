# boxctl: timeout=300
# boxctl: timeout=300
# loop session: why some rollout decisions cannot be shortened to their first K layouts (12 of azure6's records, read-only).
W=$HOME/work/loop; PY=$W/venv/bin/python
nice -n 10 "$PY" - <<'PY'
import gzip, json, glob, base64, collections
import numpy as np
c = collections.Counter(); ex = []
for f in sorted(glob.glob('/tmp/kt/eps/*.json.gz')):
    d = json.load(gzip.open(f, 'rt'))
    for e in d['unique_tables'].values():
        for t in e['tables']:
            for a in t['actions']:
                n = a.get('x8')
                if not n or n.get('mode') != 'rollout' or len(n.get('cards') or ()) < 2:
                    continue
                cap = n.get('cap')
                if not cap:
                    c['no cap'] += 1; continue
                k, m = cap['shape']
                tt = np.frombuffer(base64.b64decode(cap['t']), np.int8).reshape(k, m)
                first_missing = int(np.argmax((tt < 0).any(1))) if (tt < 0).any() else k
                c[('rows', min(k, 128) // 8 * 8, 'complete rows', min(first_missing, 64) // 8 * 8)] += 1
                if len(ex) < 6:
                    ex.append(dict(rows=k, cands=m, layouts=n.get('layouts'), n=n.get('n'), first_missing=first_missing, ply=a.get('ply')))
for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:14]:
    print(v, k)
for e in ex: print(e)
PY
