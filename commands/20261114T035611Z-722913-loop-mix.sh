# boxctl: timeout=600
# boxctl: timeout=600
# loop session (read-only, Nice 10, second checkout): what playing a random one of its near-equal candidates would cost
# SiD (rollout) Stu R3 by its own rollout values, on l3-p's records (against Gen 8, deals 500-999), and the action fields.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 45e93dfb6d55fb0ec7a4260dedcaa18b52845cd3
cd "$S2"
"$PY" - <<'PY'
import glob, gzip, json, os
f = sorted(glob.glob(os.path.expanduser('~/work/loop/runs/l3-p/episodes/*.json.gz')))[0]
d = json.load(gzip.open(f, 'rt')); e = next(iter(d['unique_tables'].values())); t = e['tables'][0]
a = next(x for x in t['actions'] if (x.get('x8') or {}).get('mode') == 'rollout' and len(x['x8'].get('cards', [])) > 1)
print('table keys', sorted(t)[:12]); print('action keys', sorted(a)[:16]); print('x8 keys', sorted(a['x8'])); print('role', a.get('role'), 'player', a.get('player'), '| candidate', d.get('candidate'))
PY
nice -n 10 "$PY" training/rollout-loop-20261113/bench/mix_budget.py "$W/runs/l3-p/episodes" --bot candidate
date -u +%FT%TZ
