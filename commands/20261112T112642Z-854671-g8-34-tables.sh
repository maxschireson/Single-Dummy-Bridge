# boxctl: timeout=300
# boxctl: timeout=300
# g8 (azure4, mine until 13:00 UTC): double-dummy tables for ten more seeds of 4,000 deals (401 to 410), as a unit.
# They are the labels for fitting the rule bidder's trick estimate. Files go to the results branch, folder dd/.
set -uo pipefail
G=$HOME/work/g8; D=$G/src-tune
mkdir -p "$G/pub/dd"
cat > "$G/tables.sh" <<'SH'
#!/usr/bin/env bash
G=$HOME/work/g8; D=$G/src-tune; PY=$HOME/work/venv/bin/python
cd "$D" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
for seed in 401 402 403 404 405 406 407 408 409 410; do
  "$PY" - "$seed" <<'PY' >> "$G/tables.log" 2>&1
import sys, time, importlib.util
sys.path.insert(0, '.')
spec = importlib.util.spec_from_file_location('tune_rule_bidder', 'scripts/tune_rule_bidder.py'); T = importlib.util.module_from_spec(spec)
sys.modules['tune_rule_bidder'] = T; spec.loader.exec_module(T)
seed = int(sys.argv[1]); t = time.time()
T.dd_tables(seed, 4000, __import__('os').path.expanduser('~/work/g8/ddcache'), 8)
print('seed', seed, 'done in', round(time.time() - t), 's', flush=True)
PY
  cp -f "$G/ddcache/dd-$seed.npz" "$G/pub/dd/" 2>/dev/null
done
for seed in 301 302 307; do cp -f "$G/ddcache/dd-$seed.npz" "$G/pub/dd/" 2>/dev/null; done
SH
chmod +x "$G/tables.sh"
sudo systemctl stop g8-tables 2>/dev/null; sudo systemctl reset-failed g8-tables 2>/dev/null
sudo systemd-run --quiet --unit=g8-tables --uid="$(id -un)" --setenv=HOME="$HOME" --working-directory="$G" -- "$G/tables.sh"
sleep 100; echo "tables unit: $(systemctl is-active g8-tables)"; tail -3 "$G/tables.log" 2>/dev/null; ls "$G/ddcache" | tr '\n' ' '
