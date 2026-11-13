# boxctl: timeout=900
# boxctl: timeout=1200
# loop session (Max, 19:32 UTC: "Prioritize bf16 first"): the collection plays with the nets in bf16 (3b37f15:
# gen7_net.Bf16Forward through torch, opt-in by ~/work/loop/BF16 for runs named sp*; measurement runs stay fp32).
# torch (CPU build) into the loop venv; the chains restart; boards in hand are lost, every finished board kept.
# CHECK=1, first eight test tables of each collection bot on the patched code, to compare their cards with this
# afternoon's fingerprints (pure Stu 98816ce14af8b825 on every box). The chains restart on it; boards in hand are lost,
# every finished board kept.
set -euo pipefail
COMMIT=57eb87cb36364263f37cc3baa67be8711229faf3
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
"$PY" -c "import torch" 2>/dev/null || "$W/venv/bin/pip" install -q torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | tail -2
"$PY" -c "import torch; print(\"torch\", torch.__version__)"
touch "$W/BF16"
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
