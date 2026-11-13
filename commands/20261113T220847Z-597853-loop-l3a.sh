# boxctl: timeout=300
# boxctl: timeout=300
# loop session: azure5's chains to recycled workers (~/work/loop/RECYCLE 30, as on the other four boxes since 21:30 UTC)
# and the interim net alone on gate deals 500-999 against Gen 8 card play (rungs.sh jobs-azure5-r3a.txt in a unit of its
# own: the collection pauses for the rung, about 15 minutes, and restarts after it on the recycled workers).
set -euo pipefail
COMMIT=1e899964952459f25e11aa5ff3f7a8e676f67acb
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
free -m | sed -n 2p
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo 30 > "$W/RECYCLE"
ls -la "$S/models/cardplay/stu-net-r3a-20261113/policy.npz" | cut -c1-120
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure5-r3a.txt azure5
sleep 20; systemctl is-active loop-rungs loop-collect loop-collect-b loop-publish | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-200; date -u +%FT%TZ
