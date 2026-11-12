# boxctl: timeout=900
# boxctl: timeout=900
# g8: tune the rule bidder (the project's own Precision-style bidder) for double-dummy IMPs against the house bidder:
# 4,000 deals to tune on, 4,000 unseen deals to report on. Runs as unit g8-tune on every core; the match queue is
# paused for it (after the match that is finishing) and started again when it ends. Results: ~/work/g8/tune and the
# results branch (folder tune/).
set -uo pipefail
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery; D=$G/src-tune; BOX=$BOXCTL_BOX
for i in $(seq 1 60); do grep -q "end c2-7s-v41-v-v4" "$G/queue.log" && break; sleep 10; done
sudo systemctl stop g8-queue
[ -d "$D/.git" ] || { git init -q "$D"; git -C "$D" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; }
git -C "$D" fetch -q --depth 1 origin ca4fe531eaa7f2d18d18bc6c4df64d2ab6e35945 && git -C "$D" checkout -q FETCH_HEAD || { echo "could not check out"; exit 1; }
cp "$G/src/bridge_harness/libbridge_dds.so" "$D/bridge_harness/" || exit 1
mkdir -p "$G/tune" "$G/pub/tune"
cat > "$G/tune.sh" <<'SH'
#!/usr/bin/env bash
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery; BOX=$1
cd "$G/src-tune" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
"$PY" -u scripts/tune_rule_bidder.py tune --source "$CAP" --deals 4000 --seed 301 --test-deals 4000 --test-seed 302 \
    --cache "$G/ddcache" --workers 8 --passes 3 --out "$G/tune/precision-tuned.json" > "$G/tune/tune.log" 2>&1
echo "exit $?" >> "$G/tune/tune.log"
cp -f "$G/tune/tune.log" "$G/tune/precision-tuned.json" "$G/pub/tune/" 2>/dev/null
sudo systemd-run --quiet --unit=g8-queue --uid="$(id -un)" --setenv=HOME="$HOME" --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 \
  --setenv=MKL_NUM_THREADS=1 --property=Restart=on-failure --property=RestartSec=20 --working-directory="$G" -- "$G/queue.sh"
SH
chmod +x "$G/tune.sh"
sudo systemctl stop g8-tune 2>/dev/null; sudo systemctl reset-failed g8-tune 2>/dev/null
sudo systemd-run --quiet --unit=g8-tune --uid="$(id -un)" --setenv=HOME="$HOME" --working-directory="$G" -- "$G/tune.sh" "$BOX"
sleep 45
echo "tune: $(systemctl is-active g8-tune); queue: $(systemctl is-active g8-queue)"; tail -3 "$G/tune/tune.log" | cut -c1-200; tail -2 "$G/queue.log" | cut -c1-140
