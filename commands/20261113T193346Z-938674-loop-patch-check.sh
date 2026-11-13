# boxctl: timeout=1200
# boxctl: timeout=1200
CHECK=1
# loop session: the forward-pass patch (ecb813a: same numbers to 4e-6, 2.5x the rollout net) into the collection. With
# CHECK=1, first eight test tables of each collection bot on the patched code, to compare their cards with this
# afternoon's fingerprints (pure Stu 98816ce14af8b825 on every box). The chains restart on it; boards in hand are lost,
# every finished board kept.
set -euo pipefail
COMMIT=ecb813acfcfeb5e6a8f0d678853011a028d377b3
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
if [ "${CHECK:-0}" = 1 ]; then
  sudo systemctl stop loop-collect loop-collect-b
  cd "$S"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
  for t in "pf-one stu0-pa~stu0-pb 8" "pf-oner stu0-pra~stu0-prb 8"; do
    set -- $t; rm -rf "$W/runs/$1"
    timeout 900 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$2" --deals "$3" --first 0 --seed 9000 --workers 8 --episodes --one-room --out "$W/runs/$1" 2>&1 | tail -1 | cut -c1-110
  done
  "$PY" - <<'PY'
import glob, gzip, json, os, hashlib
W = os.path.expanduser('~/work/loop/runs')
for run in ('pf-one', 'pf-oner'):
    rows = [json.loads(l) for l in open(f'{W}/{run}/results.jsonl')]
    cards = hashlib.sha256()
    for f in sorted(glob.glob(f'{W}/{run}/episodes/*')):
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            cards.update(' '.join(a['card'] for a in e['tables'][0]['actions']).encode())
    print(run, 'boards', len(rows), 'cpu a board %.1f' % (sum(r['cpu'] for r in rows) / len(rows)), 'cards digest', cards.hexdigest()[:16])
PY
  rm -rf "$W/runs/pf-one" "$W/runs/pf-oner"
fi
B=$(cat "$W/pub/.git/HEAD" 2>/dev/null | sed 's#.*rollout-loop-\(azure[0-9]\)-.*#\1#')
sudo systemctl stop loop-collect loop-collect-b 2>/dev/null || true
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-$B.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-${B}b.txt"
sleep 20; echo "box $B: $(systemctl is-active loop-collect loop-collect-b | tr '\n' ' ')"; tail -n 2 "$W/runs.log" | cut -c1-140; date -u +%FT%TZ
