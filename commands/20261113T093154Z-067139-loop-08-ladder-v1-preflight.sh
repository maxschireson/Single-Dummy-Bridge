# boxctl: timeout=3000
# boxctl: timeout=3000
# loop session (Max, 09:24 UTC: calibrate also with rollouts sooner, heavier, and pure): test-run the five ladder bots with rollout net v1 inside (Max, 09:27 UTC),
# two boards each against Gen 8 card play, two workers at Nice 10 beside the collection, from a second checkout so the
# running collection's tree is not touched. Seed 9000, not the gate's. Prints, per bot, how its own decisions split by
# trick and method, to confirm the boundary is where the bot's name says.
set -euo pipefail
COMMIT=4a81c2f6d75009ff69bcc0623a12e40b335d82f3
W=$HOME/work/loop; S=$W/src; S2=$W/src2; PY=$W/venv/bin/python
if [ ! -d "$S2/.git" ]; then cp -a "$S" "$S2"; fi
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q "$COMMIT"
git -C "$S2" log -1 --format='source %h %s' | cut -c1-120
cd "$S2"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
for b in stu0v1 stu0v1-b50 stu0v1-r6 stu0v1-r3 stu0v1-p; do
  rm -rf "$W/runs/pf-$b"; t0=$(date +%s)
  timeout 700 nice -n 10 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$b~8p-32-v41" --deals 2 --first 0 --seed 9000 --workers 2 --episodes --out "$W/runs/pf-$b" 2>&1 | tail -1 | cut -c1-150
  echo "$b: $(( $(date +%s) - t0 )) s wall"
done
"$PY" - <<'PY'
import collections, glob, gzip, json, os
W = os.path.expanduser('~/work/loop/runs')
for b in ('stu0v1', 'stu0v1-b50', 'stu0v1-r6', 'stu0v1-r3', 'stu0v1-p'):
    by = collections.defaultdict(collections.Counter); cpu = []
    rows = [json.loads(l) for l in open(f'{W}/pf-{b}/results.jsonl')]
    for f in sorted(glob.glob(f'{W}/pf-{b}/episodes/*')):
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            for t in e['tables']:
                for a in t['actions']:
                    if a['player'] != 'candidate' or len(a.get('behavior_probabilities') or {}) < 2:
                        continue
                    trick = a['ply'] // 4 + 1
                    note = a.get('x8') or {}
                    mode = note.get('mode') or ('search' if a.get('estimates') else 'net')
                    if mode == 'blend':
                        mode = 'blend %.2f' % note.get('trust', -1)
                    g = 'lead' if a['ply'] == 0 else '1-2' if trick <= 2 else '3-5' if trick <= 5 else '6' if trick == 6 else '7-13'
                    by[g][mode] += 1
    print(b, '| boards', len(rows), '| cpu a board', round(sum(r['cpu'] for r in rows) / max(len(rows), 1), 1), '| results', [r.get('common') for r in rows])
    for g in ('lead', '1-2', '3-5', '6', '7-13'):
        print('   tricks', g, dict(by[g]))
PY
tail -n 1 "$W/runs/s0b.log" | cut -c1-140; uptime; date -u +%FT%TZ
