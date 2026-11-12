# boxctl: timeout=300
# boxctl: timeout=300
# g8: tune the rule bidder r2 (commit e9fde92) for double-dummy IMPs against the house bidder: 4,000 deals to tune
# on, 4,000 unseen deals to report on. Unit g8-tune on every core; the match queue is paused for it and started
# again when it ends. Results: ~/work/g8/tune and the results branch (folder tune/).
set -uo pipefail
G=$HOME/work/g8; D=$G/src-tune; BOX=$BOXCTL_BOX
sudo systemctl stop g8-queue 2>/dev/null
[ -d "$D/.git" ] || { git init -q "$D"; git -C "$D" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; }
git -C "$D" fetch -q --depth 1 origin e9fde92815886d1c4dcd277bbb1ecf3469505b4d && git -C "$D" checkout -q FETCH_HEAD || { echo "could not check out"; sudo systemd-run --quiet --unit=g8-queue --uid="$(id -un)" --setenv=HOME="$HOME" --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1 --property=Restart=on-failure --property=RestartSec=20 --working-directory="$G" -- "$G/queue.sh"; exit 1; }
cp "$G/src/bridge_harness/libbridge_dds.so" "$D/bridge_harness/" || exit 1
mkdir -p "$G/tune" "$G/pub/tune"
cat > "$G/tune.sh" <<'SH'
#!/usr/bin/env bash
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
cd "$G/src-tune" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
( while sleep 240; do cp -f "$G/tune/tune2.log" "$G/pub/tune/" 2>/dev/null; done ) &
COPIER=$!
"$PY" -u scripts/tune_rule_bidder.py tune --source "$CAP" --deals 4000 --seed 301 --test-deals 4000 --test-seed 302 \
    --cache "$G/ddcache" --workers 8 --passes 3 --keep 1.5 --out "$G/tune/precision-tuned-r2.json" > "$G/tune/tune2.log" 2>&1
echo "exit $?" >> "$G/tune/tune2.log"
kill $COPIER 2>/dev/null
cp -f "$G/tune/tune2.log" "$G/tune/precision-tuned-r2.json" "$G/pub/tune/" 2>/dev/null
sudo systemd-run --quiet --unit=g8-queue --uid="$(id -un)" --setenv=HOME="$HOME" --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
  --setenv=MKL_NUM_THREADS=1 --property=Restart=on-failure --property=RestartSec=20 --working-directory="$G" -- "$G/queue.sh"
SH
chmod +x "$G/tune.sh"
sudo systemctl stop g8-tune 2>/dev/null; sudo systemctl reset-failed g8-tune 2>/dev/null
sudo systemd-run --quiet --unit=g8-tune --uid="$(id -un)" --setenv=HOME="$HOME" --working-directory="$G" -- "$G/tune.sh"
sleep 200
echo "tune: $(systemctl is-active g8-tune); queue: $(systemctl is-active g8-queue)"; tail -4 "$G/tune/tune2.log" | cut -c1-330; ls "$G/ddcache" 2>/dev/null | tr '\n' ' '
