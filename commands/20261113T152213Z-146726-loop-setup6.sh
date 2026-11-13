# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session: azure6, borrowed for the collection (board, 15:21 UTC; the table session may stop it at any time). Set up
# ~/work/loop (own venv, checkout, builds, a copy of the capsule), test four boards of each collection bot, start the two
# collection chains and the publisher. Nothing of sidnet's, x8's, g8's or the table session's is changed.
set -euo pipefail
COMMIT=fd641727af6bcaa819a51ffece408bc9c40736da
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; mkdir -p "$W/runs" "$W/bin" "$W/capsule" "$W/pub"
[ -x "$W/venv/bin/python" ] || python3 -m venv "$W/venv" || "$HOME/work/venv/bin/python" -m venv "$W/venv"
"$W/venv/bin/pip" install -q numpy==2.5.4 jax==0.12.0.1 jaxlib==0.12.0.1 optax==0.2.9 scipy==1.18.1 h5py==3.16.0 2>&1 | tail -2
PY=$W/venv/bin/python
"$PY" -c "import numpy, h5py, jax, optax; print('numpy', numpy.__version__, 'h5py', h5py.__version__, 'jax', jax.__version__, 'optax', optax.__version__)"
if [ ! -d "$S/.git" ]; then git init -q "$S" && git -C "$S" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h %s' | cut -c1-120
D=$(mktemp -d); git -C "$D" init -q; git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge research/sure-trick-table-20261112
echo "sure.cpp from $(git -C "$D" rev-parse --short FETCH_HEAD)"
git -C "$D" show FETCH_HEAD:experiments/sure_tricks/sure.cpp > "$W/bin/sure.cpp"; rm -rf "$D"
g++ -O2 -march=native -std=c++17 -o "$W/bin/sure_cpp" "$W/bin/sure.cpp"
echo '0 0 8000000003 20008004000 1000400201c 3 3 2 4' | "$W/bin/sure_cpp" --value
sha256sum "$W/bin/sure.cpp" | cut -c1-20
cd "$S"
"$PY" scripts/build_dds.py > "$W/build_dds.log" 2>&1 && tail -1 "$W/build_dds.log"
for d in models/cardplay/hand-fit-scorer-v0-2026-11-11 models/cardplay/gen7-policy-v4.1-2026-11-12 models/cardplay/gen7-policy-v4-2026-11-11 models/cardplay/gen7-policy-v0-2026-11-11 models/cardplay/rollout-net-v1-20261113; do (cd $d && "$PY" restore.py | tail -1); done
(cd models/cardplay/gen5-2026-11-10 && "$PY" restore_policy.py | tail -1)
mkdir -p models/cardplay/rollout-net-v2-20261113
D=$(mktemp -d); git -C "$D" init -q; git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge transfer/rollout-net-v2-20261113
git -C "$D" show FETCH_HEAD:runs/w768/policy_epoch5.npz > models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz; rm -rf "$D"
sha256sum models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz | cut -c1-20
if [ ! -e "$W/capsule/recovery/manifest.json" ]; then C=$HOME/work/capsule-gen7-capture/recovery; echo "capsule $(du -sh "$C" | cut -f1)"; cp -a "$C" "$W/capsule/"; fi
"$PY" - <<'PY'
import hashlib, json, os
m = os.path.expanduser('~/work/loop/capsule/recovery/manifest.json')
d = json.load(open(m)); print('capsule manifest sha256', hashlib.sha256(open(m, 'rb').read()).hexdigest()[:16], 'bots', sorted(d['bots'])[:14])
PY
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
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
    print(run, 'boards', len(rows), 'tables', set(r['tables'] for r in rows), 'cpu a board', round(sum(r['cpu'] for r in rows) / len(rows), 1), 'cards digest', cards.hexdigest()[:16])
PY
rm -rf "$W/runs/pf-one" "$W/runs/pf-oner"
sudo systemctl reset-failed loop-collect loop-collect-b loop-publish 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure6.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure6b.txt"
sudo systemd-run --unit=loop-publish --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/pub.sh" azure6
sleep 60; systemctl is-active loop-collect loop-collect-b loop-publish | tr '\n' ' '; echo; tail -n 3 "$W/runs.log" | cut -c1-150; df -h ~ | tail -1; uptime | sed 's/.*load/load/'; date -u +%FT%TZ
