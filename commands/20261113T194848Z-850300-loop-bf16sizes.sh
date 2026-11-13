# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: why bf16 gave 1.13x end to end and not ~1.3x: rows/s by batch size, numpy fp32 against torch bf16,
# and the sizes of the net calls pure Stu really makes (four test tables). Collection paused for clean clocks.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
sudo systemctl stop loop-collect loop-collect-b
cd "$S"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
"$PY" - <<'PY'
import os, time, numpy as np
from bridge_harness import gen7_net as G
z = np.load(os.path.expanduser('~/work/loop/r2/val.npz'), allow_pickle=True)
b = {k: z[k][:2048] for k in G.INPUTS}
for path in ('models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz', 'models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz'):
    with np.load(path) as f:
        P = {k: f[k] for k in f.files if k not in G.BANK_KEYS and k != 'bot_vocab'}
    fast = G.Bf16Forward.make(P)
    line = []
    for n in (8, 16, 32, 64, 128, 256, 512, 1024):
        bb = {k: v[:n] for k, v in b.items()}
        def clock(f):
            f(); reps = max(5, 4000 // n); s = time.perf_counter()
            for _ in range(reps): f()
            return (time.perf_counter() - s) / reps
        t0, t1 = clock(lambda: G.forward(P, bb)), clock(lambda: fast(bb))
        line.append(f'{n}: {n / t0:.0f} / {n / t1:.0f} ({t0 / t1:.2f}x)')
    print(path.split('/')[-2], 'rows/s fp32 / bf16 by batch:', ' | '.join(line))
PY
"$PY" - <<'PY'
import collections, os, sys, time
os.environ['BRIDGE_NET_BF16'] = '1'
sys.argv = ['x8_match.py']
from bridge_harness import gen7_net as G
sizes = collections.Counter(); secs = collections.Counter()
orig = G.PolicyNet.__init__
def init(self, *a, **k):
    orig(self, *a, **k)
    run = self.run; name = os.path.basename(os.path.dirname(str(a[0])))
    def timed(batch, run=run, name=name):
        n = len(batch['state']); s = time.perf_counter(); out = run(batch)
        b = 1 << max(0, int(n - 1).bit_length()); sizes[(name, b)] += n; secs[(name, b)] += time.perf_counter() - s
        return out
    self.run = timed
G.PolicyNet.__init__ = init
import runpy, json
sys.argv = ['scripts/x8_match.py', '--source', os.path.expanduser('~/work/loop/capsule/recovery'), '--bots', 'configs/loop-bots.json', '--pair', 'stu0-pa~stu0-pb',
            '--deals', '4', '--first', '0', '--seed', '9000', '--workers', '1', '--one-room', '--out', os.path.expanduser('~/work/loop/runs/pf-sizes')]
t0 = time.process_time()
try:
    runpy.run_path('scripts/x8_match.py', run_name='__main__')
except SystemExit:
    pass
tot = time.process_time() - t0
print('total CPU %.1f s for 4 tables; net calls %.1f s (%.0f%%)' % (tot, sum(secs.values()), 100 * sum(secs.values()) / tot))
for (name, b), n in sorted(sizes.items()):
    print(f'  {name[:28]:28s} batch <= {b:5d}: {n:8d} rows, {secs[(name, b)]:6.2f} s, {n / max(secs[(name, b)], 1e-9):7.0f} rows/s')
PY
rm -rf "$W/runs/pf-sizes"
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure5b.txt"
sleep 10; systemctl is-active loop-collect loop-collect-b | tr '\n' ' '; date -u +%FT%TZ
