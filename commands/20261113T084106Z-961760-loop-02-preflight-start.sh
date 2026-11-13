# boxctl: timeout=3000
# boxctl: timeout=3000
# loop session: round 0 on azure5. Check out the loop's branch, play a preflight of the round-0 bot (four boards of
# self-play with the full records, two against Gen 8 card play), check the records hold the rollout means, and only then
# start the collection and the publisher as units.
set -euo pipefail
COMMIT=79c18459f3455338ed7816c022b7a380ae62b890
W=$HOME/work/loop; S=$W/src; PY=$W/venv/bin/python; T=training/rollout-loop-20261113
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf "$W/runs/smoke0" "$W/runs/pf-self" "$W/runs/pf-gate"
t0=$(date +%s)
timeout 1500 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair z0a-v2~z0b-v2 --deals 4 --first 0 --seed 9000 --workers 4 --episodes --out "$W/runs/pf-self" 2>&1 | tail -2 | cut -c1-400
echo "self-play preflight: $(( $(date +%s) - t0 )) s wall"
t0=$(date +%s)
timeout 1200 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair z0a-v2~8p-32-v41 --deals 2 --first 0 --seed 9000 --workers 2 --out "$W/runs/pf-gate" 2>&1 | tail -2 | cut -c1-400
echo "gate preflight: $(( $(date +%s) - t0 )) s wall"
ls -la "$W/runs/pf-self/episodes" | head -8
"$PY" - <<'PY'
import glob, gzip, json, os, sys
W = os.path.expanduser('~/work/loop/runs')
rows = [json.loads(l) for l in open(f'{W}/pf-self/results.jsonl')]
print('self-play rows', len(rows), [(r['index'], r.get('contract'), r.get('common'), round(r.get('cpu', 0), 1)) for r in rows])
for r in rows[:1]:
    print('row x8 (candidate):', json.dumps((r.get('search', {}).get('candidate', {}) or {}).get('x8'))[:400])
g = [json.loads(l) for l in open(f'{W}/pf-gate/results.jsonl')]
print('gate rows', len(g), [(r['index'], r.get('contract'), r.get('common'), round(r.get('cpu', 0), 1)) for r in g])
notes, modes = [], {}
def walk(x):
    if isinstance(x, dict):
        n = x.get('x8')
        if isinstance(n, dict) and 'mode' in n:
            notes.append(n); modes[n['mode']] = modes.get(n['mode'], 0) + 1
        for v in x.values(): walk(v)
    elif isinstance(x, list):
        for v in x: walk(v)
files = sorted(glob.glob(f'{W}/pf-self/episodes/*'))
size = sum(os.path.getsize(f) for f in files)
for f in files:
    walk(json.load(gzip.open(f, 'rt')))
print('episode files', len(files), 'bytes a board', size // max(len(files), 1), 'notes by mode', modes)
roll = [n for n in notes if n['mode'] == 'rollout' and n.get('roll') and len(n.get('cards', [])) > 1]
print('rollout notes with more than one candidate:', len(roll))
if roll:
    n = roll[len(roll) // 2]
    print('sample:', json.dumps({k: n.get(k) for k in ('trick', 'net', 'seat', 'cards', 'runs', 'prior', 'value', 'roll', 'n', 'se', 'alive', 'chosen', 'layouts', 'claim')})[:700])
    print('forks in the sample:', len(n.get('forks') or []))
ok = len(rows) == 4 and len(g) == 2 and len(files) == 4 and len(roll) >= 20 and all(len(n['roll']) == len(n['cards']) == len(n['n']) for n in roll)
print('PREFLIGHT', 'OK' if ok else 'FAILED')
sys.exit(0 if ok else 3)
PY
# the collection: round 0's bot against itself, 20,000 deals on seed 9001, full records kept; and the publisher
sudo systemctl reset-failed loop-collect loop-publish 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/run.sh" r0 z0a-v2~z0b-v2 9001 0 20000 8 --episodes
sudo systemd-run --unit=loop-publish --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$S/$T/pub.sh" azure5
sleep 20
systemctl is-active loop-collect loop-publish; tail -n 2 "$W/runs.log"; uptime; date -u +%FT%TZ
