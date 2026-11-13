# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: round 1's net onto azure3 and its rungs into the ladder. Fetch train-r1/policy.npz from azure5's transfer
# branch (check its sha256), check out the job file with l1-stu1, l1-p, l1-n after the deciding pair, test the three
# round-1 bots on two boards each, restart the chain. Rungs already played are kept.
set -euo pipefail
COMMIT=8fa49a855563dd55c5cf9a4177961824bb823a8d
WANT=a9ee66def78cea60caa54b8268791efead51e30184f2b8806f6bd8ce9932c53b
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; PY=$W/venv/bin/python
D=$(mktemp -d); git -C "$D" init -q; git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge transfer/rollout-loop-azure5-20261113
mkdir -p "$S/models/cardplay/stu-net-r1-20261113"
git -C "$D" show FETCH_HEAD:train-r1/policy.npz > "$S/models/cardplay/stu-net-r1-20261113/policy.npz"; rm -rf "$D"
GOT=$(sha256sum "$S/models/cardplay/stu-net-r1-20261113/policy.npz" | cut -c1-64)
[ "$GOT" = "$WANT" ] || { echo "sha256 mismatch: $GOT"; exit 1; }
echo "round 1's net in place, sha256 ${GOT:0:16}"
sudo systemctl stop loop-chain || true
tail -n 1 "$W/runs.log" | cut -c1-140; echo "l0-stu0 at $(wc -l < "$W/runs/l0-stu0/results.jsonl") boards"
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-110
cd "$S"
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
for b in stu1a stu1-p stu1-n; do
  rm -rf "$W/runs/pf-$b"
  timeout 600 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair "$b~8p-32-v41" --deals 2 --first 0 --seed 9000 --workers 2 --episodes --out "$W/runs/pf-$b" 2>&1 | tail -1 | cut -c1-140
done
"$PY" - <<'PY'
import collections, glob, gzip, json, os, sys
W = os.path.expanduser('~/work/loop/runs'); ok = True
for b in ('stu1a', 'stu1-p', 'stu1-n'):
    modes = collections.Counter(); nets = set(); rows = [json.loads(l) for l in open(f'{W}/pf-{b}/results.jsonl')]
    for f in sorted(glob.glob(f'{W}/pf-{b}/episodes/*')):
        d = json.load(gzip.open(f, 'rt'))
        for e in d['unique_tables'].values():
            for a in e['tables'][0]['actions']:
                if a['player'] == 'candidate' and len(a.get('behavior_probabilities') or {}) > 1:
                    n = a.get('x8') or {}
                    modes[n.get('mode') or ('search' if a.get('estimates') else 'net')] += 1
                    if n.get('net'): nets.add(n['net'])
    print(b, 'boards', len(rows), dict(modes), 'rollout net', sorted(nets))
    ok &= len(rows) == 2
print('ROUND 1 BOTS', 'OK' if ok else 'FAILED'); sys.exit(0 if ok else 3)
PY
rm -rf "$W"/runs/pf-stu1a "$W"/runs/pf-stu1-p "$W"/runs/pf-stu1-n
sudo systemctl reset-failed loop-chain 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/chain.sh" "$T/jobs-azure3.txt"
sleep 40; systemctl is-active loop-chain loop-publish | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-150; date -u +%FT%TZ
