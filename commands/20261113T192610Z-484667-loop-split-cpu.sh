# boxctl: timeout=300
# boxctl: timeout=300
# loop session: where pure Stu's CPU goes in the collection (read-only): per table, the rollouts' own clock against the
# table's CPU, from 60 recent records of sp0 (net's lead) and spr0 (rolled lead). And the CPU's vector features.
W=$HOME/work/loop
lscpu | grep -E "Model name|^CPU\(s\)|L2 cache|L3 cache" | sed 's/  */ /g'
lscpu | grep -o -E "avx512_bf16|avx512_vnni|avx_vnni|amx_bf16|amx_int8|avx512f |avx512_fp16" | sort -u | tr '\n' ' '; echo
"$W/venv/bin/python" - <<'PY'
import glob, gzip, json, os, collections
W = os.path.expanduser('~/work/loop/runs')
for run in ('sp0', 'spr0'):
    files = sorted(glob.glob(f'{W}/{run}/episodes/*.json.gz'), key=os.path.getmtime)[-60:]
    rows = {json.loads(l)['index']: json.loads(l) for l in open(f'{W}/{run}/results.jsonl')}
    tot = collections.Counter(); cpu = 0.; n = 0; nrows = 0; modes = collections.Counter(); dec = 0
    for f in files:
        d = json.load(gzip.open(f, 'rt'))
        r = rows.get(d['index'])
        if not r: continue
        n += 1; cpu += r['cpu']
        for e in d['unique_tables'].values():
            for t in e.get('tables', [])[:1]:
                for a in t['actions']:
                    dec += len(a.get('behavior_probabilities') or {}) > 1
                    x = a.get('x8') or {}
                    if x.get('mode'): modes[x['mode']] += 1
                    for k, v in (x.get('seconds') or {}).items():
                        tot[k] += v
                    nrows += x.get('net_rows', 0) or 0
                    tot['_action_cpu'] += a.get('cpu_seconds', 0) or 0
    print(run, 'tables', n, '| cpu a table %.1f' % (cpu / n), '| decisions a table %.1f' % (dec / n), '| modes a table', {k: round(v / n, 1) for k, v in modes.items()})
    print('   seconds a table by part:', {k: round(v / n, 2) for k, v in sorted(tot.items())}, '| net rows a table %d' % (nrows / n))
    roll = sum(v for k, v in tot.items() if k.startswith('roll')) / n
    print('   rollouts share of table cpu %.0f%% | net rows/s inside rollouts %.0f' % (100 * roll / (cpu / n), nrows / n / max(roll, 1e-9)))
PY
