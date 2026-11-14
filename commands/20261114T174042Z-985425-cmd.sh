# boxctl: timeout=300
# loop session (Max, 17:34 UTC: "likely adopt"): round 4's net (stu4c, trained only on bots) takes over this box's one-net
# self-play. The collection stops, the source moves to 30e30af (sp4t/sp4tb in jobs-azure2.txt, the stu4c twins), round 4c's
# net is fetched from azure5's transfer branch (get_net.sh 4c), and the collection starts again.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; BOX=azure2; COMMIT=30e30af88ea196b8189ff39491c83cf531797868
SHA4C=e4b689c87db2f56b98221a491757dbf348ddaea066e016f06a9331fc671197f2
systemctl list-units --plain --no-legend 'loop-*' | awk '{print $1, $4}' | tr '\n' ' '; echo
tail -n 2 "$W/runs.log" | cut -c1-150
sudo systemctl stop loop-collect loop-collect-b 2>/dev/null || true; sleep 5
git -C "$S" status --short | head -5
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
cd "$S"; bash $T/get_net.sh 4c "$SHA4C"
grep -v '^#' "$S/$T/jobs-$BOX.txt" | grep . | tail -2
echo "$(date -u +%FT%TZ) round 4's net (stu4c) takes over the one-net self-play (source ${COMMIT:0:7}; Max, 17:34 UTC: likely adopt)" >> "$W/runs.log"
sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-$BOX.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-${BOX}b.txt"
sleep 60; systemctl is-active loop-collect | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-170; pgrep -u "$USER" -fc scripts/x8_match.py || true; date -u +%FT%TZ
