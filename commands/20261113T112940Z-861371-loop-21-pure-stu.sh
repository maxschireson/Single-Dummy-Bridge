# boxctl: timeout=1800
# boxctl: timeout=1800
# loop session (Max, 11:25 UTC: "Should we just do pure Stu (with single dummy guarantee)?"): azure5's collection after
# the ladder's deciding comparison is pure Stu against itself. Check out the new job file, test pure Stu's self-play pair
# and the searched-lead variant on two boards each, restart the chain (the comparison in hand resumes; its boards are kept).
set -euo pipefail
COMMIT=e00923e4e538d7081d8e89fdf4d491fdf373f36a
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
sudo systemctl stop loop-collect || true
tail -n 1 "$W/runs.log" | cut -c1-140; echo "l0b-stu0 at $(wc -l < "$W/runs/l0b-stu0/results.jsonl") boards"
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
for t in "pf-pp stu0-pa~stu0-pb 4" "pf-pl stu0-pl~8p-32-v41 2"; do
  set -- $t; rm -rf "$W/runs/$1"; t0=$(date +%s)
  timeout 900 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$2" --deals "$3" --first 0 --seed 9000 --workers 4 --episodes --out "$W/runs/$1" 2>&1 | tail -1 | cut -c1-150
  echo "$1: $(( $(date +%s) - t0 )) s wall"
done
"$PY" - <<'PY'
import collections, glob, gzip, json, os, sys
W = os.path.expanduser('~/work/loop/runs'); ok = True
for run, role in (('pf-pp', 'candidate'), ('pf-pp', 'opponent'), ('pf-pl', 'candidate')):
    by = collections.defaultdict(collections.Counter); caps = 0
    files = sorted(glob.glob(f'{W}/{run}/episodes/*'))
    for f in files:
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            for a in e['tables'][0]['actions']:
                if a['player'] == role and len(a.get('behavior_probabilities') or {}) > 1:
                    n = a.get('x8') or {}
                    by['lead' if a['ply'] == 0 else 'later'][n.get('mode') or ('search' if a.get('estimates') else 'net')] += 1
                    caps += bool(n.get('cap'))
    rows = [json.loads(l) for l in open(f'{W}/{run}/results.jsonl')]
    print(run, role, '| lead', dict(by['lead']), '| later', dict(by['later']), '| decisions with per-layout results', caps, '| bytes a board', sum(map(os.path.getsize, files)) // max(len(files), 1), '| cpu a board', round(sum(r['cpu'] for r in rows) / max(len(rows), 1), 1))
    ok &= len(rows) > 0 and 'search' not in by['later'] and (set(by['lead']) <= ({'search'} if run == 'pf-pl' else {'net'}))
print('PURE STU BOTS', 'OK' if ok else 'CHECK FAILED'); sys.exit(0 if ok else 3)
PY
rm -rf "$W/runs/pf-pp" "$W/runs/pf-pl"
sudo systemctl reset-failed loop-collect 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sleep 40; systemctl is-active loop-collect loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
