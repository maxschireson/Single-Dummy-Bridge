# boxctl: timeout=240
# loop session (Max, 17:57 UTC: "if it's by rows we should make sure we have full rows"): read-only. What a record costs and
# holds: CPU and tables (root, forks) of a sample of the arena's records against this box's self-play records.
set -uo pipefail
W=$HOME/work/loop
python3 - "$W" <<'PY'
import gzip, json, glob, random, sys, os
W = sys.argv[1]
random.seed(4)
def look(files, name):
    n = cpu_base = cpu_branch = tables = roots = forks = acts = est = fresh = 0
    cpu_tab = 0.
    kinds = {}
    for f in files:
        try:
            d = json.load(gzip.open(f, 'rt'))
        except Exception:
            continue
        if not isinstance(d, dict) or 'unique_tables' not in d:
            continue
        n += 1
        cpu_base += d.get('base_cpu') or 0; cpu_branch += d.get('branch_cpu') or 0
        for e in d['unique_tables'].values():
            for t in e.get('tables') or ():
                tables += 1
                k = (t.get('depth', 0), t.get('fork_kind'))
                kinds[k] = kinds.get(k, 0) + 1
                root = not t.get('depth', 0) and not t.get('fork_kind')
                roots += root; forks += not root
                cpu_tab += t.get('cpu_seconds') or 0
                a = t.get('actions') or ()
                acts += len(a)
                est += sum(1 for x in a if x.get('estimates') or (x.get('x8') or {}).get('mode') == 'rollout')
    if not n:
        print(name, 'no records'); return
    print('%-28s %4d records | tables a record %.1f (root %.1f, forks %.1f) | decisions with values a record %.0f | CPU-s a record: base %.1f + branch %.1f = %.1f (tables sum %.1f)'
          % (name, n, tables / n, roots / n, forks / n, est / n, cpu_base / n, cpu_branch / n, (cpu_base + cpu_branch) / n, cpu_tab / n))
    print('   tables by (depth, fork kind):', dict(sorted(kinds.items(), key=lambda kv: -kv[1])[:6]))
arena = glob.glob(W + '/r4arena/eps/*.json.gz')
by = {}
for f in arena:
    by.setdefault(os.path.basename(f).split('__')[0][:34], []).append(f)
print(len(arena), 'arena records;', len(by), 'name prefixes')
look(random.sample(arena, min(250, len(arena))), 'arena, a sample')
for run in ('sg8t1', 'sg8t2', 'sp3s', 'sp0'):
    fs = sorted(glob.glob(W + '/runs/%s/episodes/*.json.gz' % run))
    if fs: look(random.sample(fs, min(150, len(fs))), 'self-play ' + run)
PY
date -u +%T
