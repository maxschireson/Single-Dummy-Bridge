# boxctl: timeout=3600
# boxctl: timeout=3600
# loop session: round 1's net forgot some of the other bots (8s-32's exact card 82.2% to 81.1%). Four more nets on the same
# training and held-out rows (~/work/loop/r1): the whole net at two lower rates, and only Stu's two vectors at two rates
# (nothing else can move). Nice 10, four threads, beside the collection.
set -euo pipefail
COMMIT=5046a7d9217ba9f85fcee531c45825aadffd82e8
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; R=$W/r1
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q "$COMMIT"
git -C "$S2" log -1 --format='source %h %s' | cut -c1-110
cd "$S2"
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
V2=models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz
train() {   # folder epochs rate [more options]
  local name=$1 ep=$2 lr=$3; shift 3
  nice -n 10 "$PY" scripts/train_rollout_net.py --data "$R/train.npz" --all-train --val-data "$R/val.npz" --out "$R/$name" --width 768 \
    --epochs "$ep" --patience 2 --batch 256 --lr "$lr" --id-dropout 0 --save-epochs --init "$V2" --init-as stu0=8s-32 "$@" > "$R/$name.log" 2>&1 \
    || { echo "training $name failed"; tail -n 4 "$R/$name.log"; }
}
t0=$(date +%s)
train full-5e5 4 5e-5
train full-1e4 4 1e-4
train vec-3e3 8 3e-3 --only-vectors stu0
train vec-1e2 8 1e-2 --only-vectors stu0
echo "training: $(( $(date +%s) - t0 )) s"
"$PY" - "$R" <<'PY'
import json, os, sys
R = sys.argv[1]
print('%-10s %5s | %-22s | %-22s | %-22s | %-15s | %s' % ('net', 'epoch', 'stu0 log-loss, card', '8s-32 log-loss, card', '71s-32', '1 (Gen 1)', 'stu0 from trick 7; given up'))
for name in ('before', 'net', 'full-1e4', 'full-5e5', 'vec-3e3', 'vec-1e2'):
    p = f'{R}/{name}/metrics.json'
    if not os.path.exists(p):
        print(name, 'missing'); continue
    m = json.load(open(p)); v = m['validation']['by_bot']
    f = lambda b: '%.4f %.4f' % (v[b]['nll'], v[b]['agree'])
    hist = [(h['epoch'], h['val']['nll']) for h in m['history']]
    print('%-10s %5s | %-22s | %-22s | %-22s | %-15s | %s' % (name, m.get('selected_epoch'), f('stu0'), f('8s-32'), f('71s-32'), f('1'), v['stu0'].get('regret')), hist if name.startswith('vec') else '')
PY
tail -n 1 "$W/runs/s0.log" | cut -c1-110; date -u +%FT%TZ
