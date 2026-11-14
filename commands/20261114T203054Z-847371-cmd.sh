# boxctl: timeout=420
# loop session (Max, 20:18 UTC: "put it to work on whatever is most productive"): azure7 runs the width study's compute control.
# A unit (loop-pool) copies the pool's row files from azure5 over the private network (checked by sha256), then trains rollout
# net v2's recipe at its own width (768) for 15 epochs instead of 5 on the same rows and held-out deals (exp-width/w768x15),
# then starts this box's Gen 8 collection (jobs-azure7.txt) with its publisher and row publisher.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; COMMIT=5f887f18ddd6988ac40083a0f7ba2a3a60a02178
git -C "$S" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
getent hosts Bridgebots5 | awk '{print "Bridgebots5 resolves on the private network:", ($1 ~ /^10\./ ? "yes" : "no")}'
cat > "$W/pool.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; PY=$W/venv/bin/python; D=$HOME/work/plan/rnet2w/data
mkdir -p "$D" "$W/exp-width" "$W/pub/exp-width"
log() { echo "$(date -u +%FT%TZ) $*" >> "$W/runs.log"; }
log "copying the pool's rows from azure5 (train.npz, freshB.npz)"
for f in freshB.npz train.npz; do
  curl -sS --fail --retry 3 -o "$D/$f.part" "http://Bridgebots5:8765/$f" && mv "$D/$f.part" "$D/$f" || { log "copy of $f failed"; exit 1; }
done
echo "ddaad247b91ef815c0dd0cbe5b65bb63af956617e36173719b37fa451a8e237c  $D/train.npz" > /tmp/pool.sha
echo "511d1d8cade0564e96a5919b39957d90b33216ffd3bc3dd61abfc5b5deb995db  $D/freshB.npz" >> /tmp/pool.sha
sha256sum -c /tmp/pool.sha >> "$W/runs.log" 2>&1 || { log "the pool's copy does not match azure5's sha256"; exit 1; }
log "width study, compute control: v2's recipe, 768 wide, 15 epochs on the pool (exp-width/w768x15)"
cd "$S"; export OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8
"$PY" scripts/train_rollout_net.py --data "$D/train.npz" --all-train --val-data "$D/freshB.npz" --kind suit --width 768 --epochs 15 \
  --save-epochs --compare models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz --out "$W/exp-width/w768x15" > "$W/exp-width/w768x15.log" 2>&1
rc=$?
cp -f "$W/exp-width/w768x15.log" "$W/exp-width/w768x15/metrics.json" "$W/pub/exp-width/" 2>/dev/null
log "compute control ended: exit $rc; Gen 8's self-play starts"
sudo systemctl reset-failed loop-collect loop-rows 2>/dev/null
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure7.txt"
# shellcheck disable=SC2046
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$S/$T/rows.sh" $(grep -v '^#' "$S/$T/jobs-azure7.txt" | awk '{print $1}' | tr '\n' ' ')
EOS
sudo systemctl reset-failed loop-pool loop-publish 2>/dev/null || true
sudo systemd-run --unit=loop-publish --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$S/$T/pub.sh" azure7
sudo systemd-run --unit=loop-pool --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/pool.sh"
sleep 240; systemctl is-active loop-pool loop-publish | tr '\n' ' '; tail -n 4 "$W/runs.log" | cut -c1-150; ls -la $HOME/work/plan/rnet2w/data/ | tail -n 3 | cut -c1-110; date -u +%FT%TZ
