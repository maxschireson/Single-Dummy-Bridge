# boxctl: timeout=300
# boxctl: timeout=300
# loop session: how many hand-type classes the layout reader scores at each decision of pure Stu (read-only).
W=$HOME/work/loop
"$W/venv/bin/python" - <<'PY'
import glob, gzip, json, os, collections
W = os.path.expanduser('~/work/loop/runs')
files = sorted(glob.glob(f'{W}/sp0/episodes/*.json.gz'), key=os.path.getmtime)[-40:]
by_trick = collections.defaultdict(list); keys = collections.Counter(); first = []
for f in files:
    d = json.load(gzip.open(f, 'rt'))
    for e in d['unique_tables'].values():
        for t in e.get('tables', [])[:1]:
            seen = set()
            for a in t['actions']:
                g = a.get('gen6') or {}
                keys.update(g.keys())
                if 'classes' in g:
                    by_trick[a['ply'] // 4 + 1].append(g['classes'])
                    if a['player'] not in seen:
                        seen.add(a['player']); first.append(g['classes'])
print('gen6 note keys:', dict(keys.most_common(14)))
print('classes scored, by trick (mean, max, decisions):', {k: (round(sum(v) / len(v)), max(v), len(v)) for k, v in sorted(by_trick.items())})
print('first decision of each side after dummy: mean %.0f, max %d, n %d' % (sum(first) / max(len(first), 1), max(first or [0]), len(first)))
PY
