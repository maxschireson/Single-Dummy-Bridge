# boxctl: timeout=200
# boxctl: timeout=200
# g8 (azure4, mine until 13:00 UTC): after the running table job, record the rule bidder's states on seeds 401-410
# (for fitting its trick estimate), then tables and states for ten more seeds (411-420). Small files, to est/ and dd/.
set -uo pipefail
G=$HOME/work/g8; D=$G/src-tune
mkdir -p "$G/pub/est" "$G/pub/dd" "$G/est"
cat > "$G/states.sh" <<'SH'
#!/usr/bin/env bash
G=$HOME/work/g8; D=$G/src-tune; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
while systemctl is-active --quiet g8-tables; do sleep 5; done
cd "$D" || exit 1
git fetch -q --depth 1 origin 136211c31a4bc02400db8d5fc3e3f97e7e304c83 && git checkout -q FETCH_HEAD || { echo "could not check out" >> "$G/states.log"; exit 1; }
echo "source $(git rev-parse --short HEAD)" >> "$G/states.log"
"$PY" scripts/fit_rule_estimator.py dump --source "$CAP" --seeds 401,402,403,404,405,406,407,408,409,410 --deals 4000 \
  --settings configs/rule-systems/precision.json --estimate "" --workers 8 --out "$G/est/states-401-410.npz" >> "$G/states.log" 2>&1
cp -f "$G/est/states-401-410.npz" "$G/pub/est/"; cp -f "$G"/ddcache/dd-4*.npz "$G"/ddcache/dd-30[127].npz "$G/pub/dd/" 2>/dev/null
for seed in 411 412 413 414 415 416 417 418 419 420; do
  "$PY" - "$seed" <<'PY' >> "$G/states.log" 2>&1
import sys, time, importlib.util
sys.path.insert(0, '.')
spec = importlib.util.spec_from_file_location('tune_rule_bidder', 'scripts/tune_rule_bidder.py'); T = importlib.util.module_from_spec(spec)
sys.modules['tune_rule_bidder'] = T; spec.loader.exec_module(T)
seed = int(sys.argv[1]); t = time.time()
T.dd_tables(seed, 4000, __import__('os').path.expanduser('~/work/g8/ddcache'), 8)
print('seed', seed, 'tables in', round(time.time() - t), 's', flush=True)
PY
  cp -f "$G/ddcache/dd-$seed.npz" "$G/pub/dd/" 2>/dev/null
done
"$PY" scripts/fit_rule_estimator.py dump --source "$CAP" --seeds 411,412,413,414,415,416,417,418,419,420 --deals 4000 \
  --settings configs/rule-systems/precision.json --estimate "" --workers 8 --out "$G/est/states-411-420.npz" >> "$G/states.log" 2>&1
cp -f "$G/est/states-411-420.npz" "$G/pub/est/"
echo done >> "$G/states.log"
SH
chmod +x "$G/states.sh"
sudo systemctl stop g8-states 2>/dev/null; sudo systemctl reset-failed g8-states 2>/dev/null
sudo systemd-run --quiet --unit=g8-states --uid="$(id -un)" --setenv=HOME="$HOME" --working-directory="$G" -- "$G/states.sh"
sleep 20; echo "states unit: $(systemctl is-active g8-states); tables unit: $(systemctl is-active g8-tables)"; tail -3 "$G/tables.log" 2>/dev/null; tail -3 "$G/states.log" 2>/dev/null; ls "$G/ddcache" | tr '\n' ' '
