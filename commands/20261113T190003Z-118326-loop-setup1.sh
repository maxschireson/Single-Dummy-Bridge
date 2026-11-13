# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session: azure1 taken for the collection on Max's authority (18:53 UTC, 13 Nov: "You can take azure 1 on my
# authority. Go ahead!", "And use azure 2."). Set up ~/work/loop (own venv, checkout, builds, a copy of the capsule),
# test four boards of each collection bot, start the two collection chains, the publisher and the rows publisher.
set -euo pipefail
# g7's 8X v3 collector failed at 16:34 UTC ("Start request repeated too quickly") and has not run since; switch off the
# automation that would start it or its follow-on cohort, by g7's own switches (next8x.sh: SWITCH_OFF; recycle8x.sh:
# RECYCLE_OFF; the run's STOP). No unit is stopped or disabled; the publisher goes on publishing the 3,986 boards it has;
# sidplay and caddy are untouched.
G=$HOME/work/gen8x; R=$HOME/work/runs/gen8-x3-azure1
touch "$G/SWITCH_OFF" "$G/RECYCLE_OFF" "$R/STOP"
echo "g7 switches: $(ls "$G" | grep -E "SWITCH_OFF|RECYCLE_OFF" | tr "\n" " ") $(ls "$R" | grep STOP)"
echo "why the collector stopped:"; tail -n 6 "$G/collector.log" 2>/dev/null | cut -c1-220
python3 -c "import json; s=json.load(open(\"$R/publisher-status.json\")); print(\"publisher: completed\", s.get(\"completed\"))" 2>/dev/null || true
COMMIT=b354072a596aceb5192ff8689c428fd51b4b7af6
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113; mkdir -p "$W/runs" "$W/bin" "$W/capsule" "$W/pub"
[ -x "$W/venv/bin/python" ] || python3 -m venv "$W/venv" || "$HOME/work/venv/bin/python" -m venv "$W/venv"
"$W/venv/bin/pip" install -q numpy==2.5.4 jax==0.12.0.1 jaxlib==0.12.0.1 optax==0.2.9 scipy==1.18.1 h5py==3.16.0 2>&1 | tail -2
PY=$W/venv/bin/python
"$PY" -c "import numpy, h5py, jax, optax; print('numpy', numpy.__version__, 'jax', jax.__version__)"
if [ ! -d "$S/.git" ]; then git init -q "$S" && git -C "$S" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; fi
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"
git -C "$S" log -1 --format='source %h' 
D=$(mktemp -d); git -C "$D" init -q; git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge research/sure-trick-table-20261112
git -C "$D" show FETCH_HEAD:experiments/sure_tricks/sure.cpp > "$W/bin/sure.cpp"; rm -rf "$D"
g++ -O2 -march=native -std=c++17 -o "$W/bin/sure_cpp" "$W/bin/sure.cpp"
sha256sum "$W/bin/sure.cpp" | cut -c1-20
cd "$S"
"$PY" scripts/build_dds.py > "$W/build_dds.log" 2>&1 && tail -1 "$W/build_dds.log"
for d in models/cardplay/hand-fit-scorer-v0-2026-11-11 models/cardplay/gen7-policy-v4.1-2026-11-12 models/cardplay/gen7-policy-v4-2026-11-11 models/cardplay/gen7-policy-v0-2026-11-11 models/cardplay/rollout-net-v1-20261113; do (cd $d && "$PY" restore.py > /dev/null); done
(cd models/cardplay/gen5-2026-11-10 && "$PY" restore_policy.py > /dev/null)
mkdir -p models/cardplay/rollout-net-v2-20261113
D=$(mktemp -d); git -C "$D" init -q; git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge transfer/rollout-net-v2-20261113
git -C "$D" show FETCH_HEAD:runs/w768/policy_epoch5.npz > models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz; rm -rf "$D"
sha256sum models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz | cut -c1-20
if [ ! -e "$W/capsule/recovery/manifest.json" ]; then cp -a "$HOME/work/capsule-gen7-capture/recovery" "$W/capsule/"; fi
sha256sum "$W/capsule/recovery/manifest.json" | cut -c1-16
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
    print(run, 'boards', len(rows), 'cards digest', cards.hexdigest()[:16])
PY
rm -rf "$W/runs/pf-one" "$W/runs/pf-oner"
sudo systemctl reset-failed loop-collect loop-collect-b loop-publish loop-rows 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure1.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-azure1b.txt"
sudo systemd-run --unit=loop-publish --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/pub.sh" azure1
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/rows.sh" $(grep -v '^#' "$T/jobs-azure1.txt" | awk '{print $1}') $(grep -v '^#' "$T/jobs-azure1b.txt" | awk '{print $1}')
sleep 60; systemctl is-active loop-collect loop-collect-b loop-publish loop-rows | tr '\n' ' '; echo; tail -n 2 "$W/runs.log" | cut -c1-140; free -g | sed -n 2p; uptime | sed 's/.*load/load/'; date -u +%FT%TZ
