# boxctl: timeout=300
# boxctl: timeout=300
# loop session: how the simulated seats take their cards, on azure3: once loop-bensession has ended, the source moves to
# fc8202f and rungs.sh plays jobs-azure3-hd.txt (the collection pauses for it and restarts after). Launched as a unit of its
# own, so this command returns at once.
set -euo pipefail
W=$HOME/work/loop; S=$W/src
cat > "$W/after-hd.sh" <<EOS
#!/usr/bin/env bash
while [ "\$(systemctl is-active loop-bensession)" = active ]; do sleep 30; done; sleep 45
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q fc8202fc96158f249b5ff14b3d0a2e959dbb5c7f
bash "$S/training/rollout-loop-20261113/rungs.sh" jobs-azure3-hd.txt azure3
EOS
cat "$W/after-hd.sh"
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/after-hd.sh"
sleep 5; echo "loop-bensession: $(systemctl is-active loop-bensession || true); loop-rungs: $(systemctl is-active loop-rungs || true)"; tail -n 2 "$W/runs.log" | cut -c1-160; date -u +%FT%TZ
