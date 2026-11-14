# boxctl: timeout=900
# loop session, on Max's word (19:00 UTC "Go!"): before this box is resized to 16 cores and 64 GB (it restarts), the width
# test's first epoch is read and kept, then its units stop and the publisher pushes. Nothing is deleted.
set -uo pipefail
W=$HOME/work/loop; L=$W/exp-width/w1536.log
for i in $(seq 1 80); do grep -q '^{"epoch": 1, "seconds"' "$L" && break; sleep 6; done
grep '^{"epoch": 1' "$L" | cut -c1-700
ls -la "$W/exp-width/w1536/" 2>/dev/null | tail -n 4 | cut -c1-110
sudo systemctl stop loop-width 2>/dev/null || true; sleep 2
pkill -u "$USER" -f scripts/train_rollout_net.py 2>/dev/null || true
mkdir -p "$W/exp-width/w1536-8core" "$W/pub/exp-width"
cp -f "$L" "$W/exp-width/w1536-8core/w1536.log"; cp -f "$W/exp-width/w1536/policy_epoch1.npz" "$W/exp-width/w1536-8core/" 2>/dev/null || true
grep -v '^epoch' "$L" | grep -v Warning > "$W/pub/exp-width/w1536-8core-epoch1.log"
echo "$(date -u +%FT%TZ) width test stopped after its first epoch: the box is resized to Standard_F16as_v6 (16 cores, 64 GB; Max, 19:00 UTC: Go) and restarts" >> "$W/runs.log"
sudo systemctl restart loop-publish; sleep 60
git -C "$W/pub" log -1 --format='publisher last commit %ci'; echo "unpushed files: $(git -C "$W/pub" status --short | wc -l)"
sudo systemctl stop loop-publish loop-collect loop-collect-b loop-rows 2>/dev/null || true
systemctl list-units --plain --no-legend 'loop-*' | awk '{print $1, $4}' | tr '\n' ';'; echo; sync; df -h / | tail -1; date -u +%FT%TZ
