# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: azure5's collection plays one table a board (the two rooms of a self-play board were the same play).
# Check out e760e5e, test --one-room on a few boards of pure Stu and of the rolled-lead bot, restart the chain (the
# comparison in hand resumes; its boards are kept).
set -euo pipefail
COMMIT=e760e5e7823699c8dabcd4cc84f0386c29fc4080
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
sudo systemctl stop loop-collect || true
tail -n 1 "$W/runs.log" | cut -c1-140; echo "l0b-p at $(wc -l < "$W/runs/l0b-p/results.jsonl") boards"
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
for t in "pf-one stu0-pa~stu0-pb 16" "pf-oner stu0-pra~stu0-prb 8"; do
  set -- $t; rm -rf "$W/runs/$1"; t0=$(date +%s)
  timeout 900 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$2" --deals "$3" --first 0 --seed 9000 --workers 8 --episodes --one-room --out "$W/runs/$1" 2>&1 | tail -1 | cut -c1-120
  echo "$1: $(( $(date +%s) - t0 )) s wall"
done
"$PY" - <<'PY'
import collections, glob, gzip, json, os
W = os.path.expanduser('~/work/loop/runs'); ok = True
for run in ('pf-one', 'pf-oner'):
    files = sorted(glob.glob(f'{W}/{run}/episodes/*'))
    tables, lead_by, sides, leads = [], collections.Counter(), collections.Counter(), collections.Counter()
    for f in files:
        d = json.load(gzip.open(f, 'rt'))
        ts = [e for e in d['unique_tables'].values() if e.get('tables')]
        tables.append(len(ts))
        for e in ts:
            sides[(d['index'] % 2, e['assignments'][0])] += 1
            acts = e['tables'][0]['actions']
            if acts:
                n = acts[0].get('x8') or {}
                leads[(n.get('mode') or ('search' if acts[0].get('estimates') else 'net')) + ('+lead' if n.get('lead') else '')] += 1
                lead_by[acts[0]['player']] += 1
    rows = [json.loads(l) for l in open(f'{W}/{run}/results.jsonl')]
    print(run, '| boards', len(rows), '| tables a board', sorted(set(tables)), set(r['tables'] for r in rows), '| IMPs fields', set(repr(r.get('common')) for r in rows),
          '| (board parity, North) ', dict(sides), '| leads', dict(leads), 'by', dict(lead_by), '| bytes a board', sum(map(os.path.getsize, files)) // max(len(files), 1), '| cpu a board', round(sum(r['cpu'] for r in rows) / max(len(rows), 1), 1))
    ok &= set(tables) <= {0, 1} and all(r.get('common') is None for r in rows) and len(rows) > 0
print('ONE ROOM', 'OK' if ok else 'CHECK FAILED')
PY
rm -rf "$W/runs/pf-one" "$W/runs/pf-oner"
sudo systemctl reset-failed loop-collect 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sleep 30; systemctl is-active loop-collect loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
