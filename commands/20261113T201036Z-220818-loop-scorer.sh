# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session: the shared hand-fit scorer (same numbers: the test tables must replay card for card in fp32) and its bf16
# path (agreement on hand types, and CPU a table end to end), on azure5 with the collection paused; then the collection
# restarts on this commit (bf16 on, as before).
set -euo pipefail
COMMIT=57eb87cb36364263f37cc3baa67be8711229faf3
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl stop loop-collect loop-collect-b
cd "$S"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
"$PY" - <<'PY'
import os, time, numpy as np
from bridge_harness import gen6_nets as N
path = 'models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz'
os.environ.pop('BRIDGE_NET_BF16', None); a = N.FitScorer(path)
os.environ['BRIDGE_NET_BF16'] = '1'; b = N.FitScorer(path)
print('scorer shapes', {k: v.shape for k, v in a.p.items() if k.startswith('W')}, '| bf16 path', b.t is not None)
rng = np.random.default_rng(0)
deck = np.zeros((40000, 52), np.int8)
for i in range(len(deck)): deck[i, rng.choice(52, 13, replace=False)] = 1
length, hon = N.hand_types(deck)
auction = ['1N', 'P', '2C', 'P', '2H', 'P', '3N', 'P', 'P', 'P']
part = a.auction_part(auction, 0, 0)
sa, sb = a.log_score(length, hon, 0., 1., part), b.log_score(length, hon, 0., 1., part)
d = np.abs(sa - sb)
w = np.exp(sa - sa.max()); w /= w.sum(); v = np.exp(sb - sb.max()); v /= v.sum()
print('log score change: mean %.4f, 99th pct %.4f, max %.4f | weights over 40,000 hands: total variation %.4f' % (d.mean(), np.percentile(d, 99), d.max(), .5 * np.abs(w - v).sum()))
for s in (a, b):
    s.log_score(length[:4096], hon[:4096], 0., 1., part); t = time.perf_counter()
    for _ in range(5): s.log_score(length, hon, 0., 1., part)
    print('bf16' if s.t is not None else 'fp32', '%.0f hand types a second' % (5 * len(length) / (time.perf_counter() - t)))
PY
for prec in fp32 bf16; do
  if [ $prec = bf16 ]; then export BRIDGE_NET_BF16=1; else unset BRIDGE_NET_BF16; fi
  rm -rf "$W/runs/pf-$prec"
  timeout 900 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair stu0-pa~stu0-pb --deals 16 --first 0 --seed 9000 --workers 8 --episodes --one-room --out "$W/runs/pf-$prec" 2>&1 | tail -1 | cut -c1-110
done
unset BRIDGE_NET_BF16
"$PY" - <<'PY'
import glob, gzip, json, os, hashlib
W = os.path.expanduser('~/work/loop/runs')
for prec in ('fp32', 'bf16'):
    rows = [json.loads(l) for l in open(f'{W}/pf-{prec}/results.jsonl')]
    h8 = hashlib.sha256(); h16 = hashlib.sha256()
    for f in sorted(glob.glob(f'{W}/pf-{prec}/episodes/*')):
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            c = ' '.join(a['card'] for a in e['tables'][0]['actions']).encode()
            h16.update(c)
            if d['index'] < 8: h8.update(c)
    print(prec, 'cpu a table %.2f' % (sum(r['cpu'] for r in rows) / len(rows)), '| first 8 tables cards digest', h8.hexdigest()[:16], '(fp32 before: 98816ce14af8b825)')
PY
rm -rf "$W/runs/pf-fp32" "$W/runs/pf-bf16"
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5b.txt"
sleep 15; systemctl is-active loop-collect loop-collect-b | tr '\n' ' '; tail -n 1 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
