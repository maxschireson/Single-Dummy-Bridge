# boxctl: timeout=300
# Install the pinned BEN server on this box (source 9b5f431, its own venv from the repo's pinned package list),
# verify the 16 model files against the repo's provenance file, and test that the server answers a bid request.
# Runs as a background unit at low CPU priority; the phase 1 collector keeps running meanwhile.
set -euo pipefail
W=$HOME/work; mkdir -p "$W/ben-setup"
cat > "$W/ben-setup/install.sh" <<'SH'
#!/usr/bin/env bash
set -uo pipefail
W=$HOME/work; SRC=$W/sdb-gen7-arena; BEN=$W/ben; BV=$W/ben-venv
COMMIT=9b5f43104aeac713a80b73513f2f2d6daf9f8769
PORT=$1; CONF=$2
say() { echo "$(date -u +%T) $*"; }
say "== source"
if [ ! -d "$BEN/.git" ]; then git init -q "$BEN" && git -C "$BEN" remote add origin https://github.com/lorserker/ben; fi
if [ "$(git -C "$BEN" rev-parse -q --verify HEAD 2>/dev/null)" != "$COMMIT" ]; then
  git -C "$BEN" fetch -q --depth 1 origin "$COMMIT" || { say "FAILED: fetch of $COMMIT"; exit 1; }
  git -C "$BEN" checkout -q FETCH_HEAD || { say "FAILED: checkout"; exit 1; }
fi
say "BEN at $(git -C "$BEN" rev-parse HEAD), $(du -sh "$BEN" | cut -f1); lfs filters: $(grep -c 'filter=lfs' "$BEN/.gitattributes" 2>/dev/null || echo 0)"
ls "$BEN/src/gameapi.py" "$BEN/src/config/default_api.conf" >/dev/null || { say "FAILED: gameapi.py or default_api.conf missing"; exit 1; }
say "== models against configs/ben-gen5-16.provenance.json"
python3 - "$SRC/configs/ben-gen5-16.provenance.json" "$BEN" <<'PY' || { echo "FAILED: model verification"; exit 1; }
import hashlib, json, sys
from pathlib import Path
prov = json.load(open(sys.argv[1])); ben = Path(sys.argv[2]); bad = 0; seen = {}
for key, m in prov['model_sha256'].items():
    p = ben / m['path']
    if m['path'] not in seen:
        seen[m['path']] = hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None
    if seen[m['path']] != m['sha256']:
        bad += 1; print('MISMATCH', key, m['path'], 'missing' if seen[m['path']] is None else seen[m['path']][:16], 'size', p.stat().st_size if p.exists() else 0)
print(f"{len(seen)} model files, {len(prov['model_sha256'])} entries, {bad} mismatches; source commit pinned {prov['source_commit'][:12]}")
sys.exit(1 if bad else 0)
PY
say "== config"
echo "$CONF sha256 $(sha256sum "$CONF" | cut -c1-64)"
say "== python environment"
[ -x "$BV/bin/python" ] || python3 -m venv "$BV"
"$BV/bin/pip" install -q --upgrade pip 2>&1 | tail -1
if ! "$BV/bin/pip" install -q -r "$SRC/configs/ben-round5-runtime-requirements.txt" > "$W/ben-setup/pip.log" 2>&1; then
  say "pinned install FAILED:"; tail -6 "$W/ben-setup/pip.log"; exit 1
fi
"$BV/bin/pip" freeze 2>/dev/null > "$W/ben-setup/ben-venv-freeze.txt"
say "packages installed: $(wc -l < "$W/ben-setup/ben-venv-freeze.txt"); differing from the pinned list: $(diff <(sort "$SRC/configs/ben-round5-runtime-requirements.txt") <(sort "$W/ben-setup/ben-venv-freeze.txt") | grep -c '^[<>]')"
diff <(sort "$SRC/configs/ben-round5-runtime-requirements.txt") <(sort "$W/ben-setup/ben-venv-freeze.txt") | grep '^[<>]' | head -8
say "== server test on 127.0.0.1:$PORT"
if (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null; then say "FAILED: something already listens on $PORT"; exit 1; fi
cd "$BEN"
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 XDG_CACHE_HOME="$W/ben-cache" \
  "$BV/bin/python" src/gameapi.py --config "$CONF" --host 127.0.0.1 --port "$PORT" --record false > "$W/ben-setup/server-test.log" 2>&1 &
pid=$!
up=0
for i in $(seq 1 120); do
  kill -0 $pid 2>/dev/null || break
  if (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null; then up=1; break; fi
  sleep 5
done
if [ $up -ne 1 ]; then say "FAILED: server did not come up"; tail -25 "$W/ben-setup/server-test.log" | cut -c1-220; kill $pid 2>/dev/null; exit 1; fi
say "listening after $((i * 5))s; memory $(ps -o rss= -p $pid | awk '{printf "%.1f GB", $1/1048576}')"
grep -i -E "dds|model|loaded|version" "$W/ben-setup/server-test.log" | grep -v -i "warning" | head -12 | cut -c1-200
start=$(date +%s.%N)
curl -s -m 600 "http://127.0.0.1:$PORT/bid?hand=AJ84.9743.A7.Q84&seat=S&dealer=S&vul=NS&ctx=&matchtype=IMP&details=true" > "$W/ben-setup/bid-test.json"
python3 - "$W/ben-setup/bid-test.json" <<'PY'
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    print('bid request answered:', {k: d[k] for k in ('bid', 'who', 'quality') if k in d}, '| keys', sorted(d)[:12])
except Exception as e:
    print('FAILED: bid request:', repr(e), open(sys.argv[1]).read()[:400])
PY
say "bid request took $(python3 -c "import time; print(round(time.time() - $start, 1))")s; server memory $(ps -o rss= -p $pid | awk '{printf "%.1f GB", $1/1048576}'), threads $(ls /proc/$pid/task | wc -l)"
kill $pid 2>/dev/null; wait $pid 2>/dev/null
say "DONE"
SH
chmod +x "$W/ben-setup/install.sh"
case "$BOXCTL_BOX" in
  azure2) PORT=8087; CONF=$W/capsule-gen7-capture/recovery/assets/ben-16.conf ;;
  azure3) PORT=8089; CONF=$W/capsule-gen7-capture/recovery/assets/ben-64.conf ;;
  *) echo "no BEN role for $BOXCTL_BOX"; exit 1 ;;
esac
systemctl is-active --quiet ben-install && { echo "already running"; exit 0; }
sudo systemctl reset-failed ben-install 2>/dev/null || true
sudo systemd-run --quiet --unit=ben-install --uid="$(id -un)" --setenv=HOME="$HOME" --nice=10 \
  --property=StandardOutput=append:"$W/ben-setup/install.log" --property=StandardError=append:"$W/ben-setup/install.log" -- "$W/ben-setup/install.sh" "$PORT" "$CONF"
sleep 15; echo "ben-install: $(systemctl is-active ben-install)"; tail -4 "$W/ben-setup/install.log"
