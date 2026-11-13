# boxctl: timeout=300
# boxctl: timeout=300
# loop session: pure Stu's time per table in the collection, before the patch, after it (fp32) and with bf16, from the
# records' own clocks (read-only). The switch times are runs.log's: patch 19:37, bf16 19:56 UTC on azure5.
W=$HOME/work/loop
lscpu | grep -E "Thread\(s\) per core|Core\(s\) per socket|Socket"
"$W/venv/bin/python" - <<'PY'
import glob, gzip, json, os, collections, datetime
W = os.path.expanduser('~/work/loop/runs')
T = lambda s: datetime.datetime.fromisoformat(s).timestamp()
cuts = [('before patch', 0, T('2026-11-13T19:30:00+00:00')), ('patch, fp32', T('2026-11-13T19:40:00+00:00'), T('2026-11-13T19:56:00+00:00')), ('+ bf16 nets', T('2026-11-13T19:59:00+00:00'), T('2026-11-13T20:12:00+00:00')), ('+ shared scorer, bf16', T('2026-11-13T20:14:00+00:00'), 1e12)]
for run in ('sp0', 'spr0'):
    rows = {}
    for l in open(f'{W}/{run}/results.jsonl'):
        r = json.loads(l); rows[r['index']] = r
    files = glob.glob(f'{W}/{run}/episodes/*.json.gz')
    for name, lo, hi in cuts:
        pick = [f for f in files if lo <= os.path.getmtime(f) < hi]
        pick = sorted(pick, key=os.path.getmtime)[-150:]
        tot = collections.Counter(); cpu = 0.; n = 0; rows_n = 0
        for f in pick:
            d = json.load(gzip.open(f, 'rt')); r = rows.get(d['index'])
            if not r: continue
            n += 1; cpu += r['cpu']
            for e in d['unique_tables'].values():
                for t in e.get('tables', [])[:1]:
                    for a in t['actions']:
                        x = a.get('x8') or {}
                        for k, v in (x.get('seconds') or {}).items(): tot[k] += v
                        rows_n += x.get('net_rows', 0) or 0
        if n:
            print(f'{run:5s} {name:22s} tables {n:4d} | cpu a table {cpu / n:5.1f} | layouts {tot["layouts"] / n:5.2f} | rollouts {tot["rollouts"] / n:5.2f} | other {(cpu - tot["layouts"] - tot["rollouts"]) / n:5.2f} | net rows/s in rollouts {rows_n / max(tot["rollouts"], 1e-9):6.0f}')
PY
