# boxctl: timeout=1800
# boxctl: timeout=1800
# loop session: the bot is Stu (Max, 09:05 UTC) and its records keep every layout's result (Max, 08:59 UTC: "See how much
# bigger / if it matters": 43 KB a board against 27 KB, same cards). Stop the collection under the old ids (run r0 stays),
# check out the new bot file, play two boards as a check, and start the collection again as run s0 from deal 1,000.
set -euo pipefail
COMMIT=29d2e6a974c06d154011911f59fb01ddbb076dbb
W=$HOME/work/loop; S=$W/src; PY=$W/venv/bin/python; T=$S/training/rollout-loop-20261113
sudo systemctl stop loop-collect || true
"$PY" - <<'PY'
import json, os
rows = [json.loads(l) for l in open(os.path.expanduser('~/work/loop/runs/r0/results.jsonl'))]
print('r0 (ids z0a-v2~z0b-v2, capture level 1) stopped at', len(rows), 'boards; highest deal', max(r['index'] for r in rows), '; cpu a board', round(sum(r['cpu'] for r in rows) / len(rows), 1))
PY
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf "$W/runs/pf-stu"
timeout 900 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair stu0a~stu0b --deals 2 --first 0 --seed 9000 --workers 2 --episodes --out "$W/runs/pf-stu" 2>&1 | tail -1 | cut -c1-200
"$PY" - <<'PY'
import glob, gzip, json, os, sys
W = os.path.expanduser('~/work/loop/runs')
rows = [json.loads(l) for l in open(f'{W}/pf-stu/results.jsonl')]
old = {json.loads(l)['index']: json.loads(l) for l in open(f'{W}/pf-self/results.jsonl')}
notes = []
def walk(x):
    if isinstance(x, dict):
        n = x.get('x8')
        if isinstance(n, dict) and 'mode' in n: notes.append(n)
        for v in x.values(): walk(v)
    elif isinstance(x, list):
        for v in x: walk(v)
files = sorted(glob.glob(f'{W}/pf-stu/episodes/*'))
for f in files: walk(json.load(gzip.open(f, 'rt')))
caps = [n for n in notes if n.get('cap')]
same = all(old[r['index']].get('contract') == r.get('contract') for r in rows if r['index'] in old)
print('stu preflight: rows', len(rows), 'records', len(files), 'bytes a board', sum(map(os.path.getsize, files)) // max(len(files), 1), 'notes', len(notes), 'with per-layout blocks', len(caps), '| same contracts as the first preflight:', same)
ok = len(rows) == 2 and len(files) == 2 and len(caps) >= 20
print('PREFLIGHT', 'OK' if ok else 'FAILED'); sys.exit(0 if ok else 3)
PY
sudo systemctl reset-failed loop-collect 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sleep 15; systemctl is-active loop-collect loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-200; ls "$W/pub" | head -12 | tr '\n' ' '; echo; git -C "$W/pub" log -1 --format='publisher last pushed %cd' --date=format:'%H:%M UTC' 2>/dev/null; date -u +%FT%TZ
