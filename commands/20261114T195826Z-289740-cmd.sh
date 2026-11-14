# boxctl: timeout=420
# loop session (Max, 19:52 UTC: go B): azure5 is now Standard_F16as_v6 (16 cores, 64 GB). The publisher starts again and the
# width test starts over from the beginning on 16 cores (v2's recipe at 1,536 wide on the pool; the 8-core run's first epoch
# is kept in exp-width/w1536-8core). When it ends the collection starts again (width.sh).
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
nproc; free -g | sed -n 2p; df -h / | tail -1
sudo systemctl reset-failed loop-publish loop-width 2>/dev/null || true
sudo systemd-run --unit=loop-publish --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$S/$T/pub.sh" azure5
sed -i 's/OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8 MKL_NUM_THREADS=8/OPENBLAS_NUM_THREADS=16 OMP_NUM_THREADS=16 MKL_NUM_THREADS=16/; s/on the pool.s rows (the collection is paused)/on the pool'"'"'s rows, 16 cores (the collection is paused)/' "$W/width.sh"
grep -n "THREADS\|width test begins" "$W/width.sh" | cut -c1-160
rm -rf "$W/exp-width/w1536"
echo "$(date -u +%FT%TZ) the box is Standard_F16as_v6 (16 cores, 64 GB); the width test starts over" >> "$W/runs.log"
sudo systemd-run --unit=loop-width --uid="$USER" --working-directory="$W/src-lc" --setenv=HOME="$HOME" -- bash "$W/width.sh"
sleep 300; systemctl is-active loop-width loop-publish | tr '\n' ' '; grep -v Warning "$W/exp-width/w1536.log" | tail -n 3 | cut -c1-160; uptime | cut -c1-80; date -u +%FT%TZ
