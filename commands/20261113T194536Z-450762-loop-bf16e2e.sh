# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session: bf16 end to end on azure5 before it goes into the collection. torch into the loop's venv; PolicyNet's bf16
# path against fp32 on held-out rows (the same net object both ways); then eight test tables of pure Stu with and
# without it, collection paused so the clocks are clean. The collection restarts on fp32 (no BF16 flag yet).
set -euo pipefail
COMMIT=3b37f15d4327da8d1f62b4cb8bf44808056d95d4
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
"$W/venv/bin/pip" install -q torch --index-url https://download.pytorch.org/whl/cpu 2>&1 | tail -2
"$PY" -c "import torch, numpy; print('torch', torch.__version__, 'numpy', numpy.__version__)"
sudo systemctl stop loop-collect loop-collect-b
cd "$S"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
"$PY" - <<'PY'
import os, numpy as np, time
from bridge_harness import gen7_net as G
from bridge_harness.gen6_nets import FitScorer
sc = FitScorer('models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz')
z = np.load(os.path.expanduser('~/work/loop/r2/val.npz'), allow_pickle=True)
pick = np.sort(np.random.default_rng(1).choice(len(z['deal']), 16384, replace=False))
b = {k: z[k][pick] for k in G.INPUTS}
b['bot_own'] = np.full(len(pick), 3, np.int32); b['bot_other'] = np.full(len(pick), 5, np.int32)
for path in ('models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz', 'models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz'):
    os.environ.pop('BRIDGE_NET_BF16', None); a = G.PolicyNet(path, sc)
    os.environ['BRIDGE_NET_BF16'] = '1'; c = G.PolicyNet(path, sc)
    bb = b if a.vocab else {k: v for k, v in b.items() if not k.startswith('bot_')}
    la, ga = a.policy_and_gap_arrays(bb); lc, gc = c.policy_and_gap_arrays(bb)
    legal = bb['legal'].astype(bool)
    print(path.split('/')[-2], a.precision, '->', c.precision, '| first card same %.2f%%' % (100 * (la.argmax(1) == lc.argmax(1)).mean()),
          '| log-prob change mean %.4f' % (np.abs(np.where(legal, la - lc, 0)).sum() / legal.sum()), '| gap change mean %.4f' % np.abs(np.where(legal, ga - gc, 0)).mean())
PY
for prec in fp32 bf16; do
  if [ $prec = bf16 ]; then export BRIDGE_NET_BF16=1; else unset BRIDGE_NET_BF16; fi
  rm -rf "$W/runs/pf-$prec"; t0=$(date +%s)
  timeout 900 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair stu0-pa~stu0-pb --deals 16 --first 0 --seed 9000 --workers 8 --episodes --one-room --out "$W/runs/pf-$prec" 2>&1 | tail -1 | cut -c1-110
  echo "$prec: $(( $(date +%s) - t0 )) s wall"
done
unset BRIDGE_NET_BF16
"$PY" - <<'PY'
import glob, gzip, json, os, hashlib
W = os.path.expanduser('~/work/loop/runs')
cards = {}
for prec in ('fp32', 'bf16'):
    rows = [json.loads(l) for l in open(f'{W}/pf-{prec}/results.jsonl')]
    seq = {}
    for f in sorted(glob.glob(f'{W}/pf-{prec}/episodes/*')):
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            seq[d['index']] = [a['card'] for a in e['tables'][0]['actions']]
    cards[prec] = seq
    x8 = [r['search']['candidate'].get('x8') or {} for r in rows]
    print(prec, 'tables', len(rows), '| cpu a table %.2f' % (sum(r['cpu'] for r in rows) / len(rows)), '| rollouts seconds a table %.2f' % (sum((a.get('seconds') or {}).get('rollouts', 0) if isinstance(a.get('seconds'), dict) else 0 for a in x8) / len(rows)))
same = sum(cards['fp32'][i] == cards['bf16'][i] for i in cards['fp32'] if i in cards['bf16'])
print('tables played identically card for card:', same, 'of', len(cards['fp32']))
PY
rm -rf "$W/runs/pf-fp32" "$W/runs/pf-bf16"
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5b.txt"
sleep 15; systemctl is-active loop-collect loop-collect-b | tr '\n' ' '; date -u +%FT%TZ
