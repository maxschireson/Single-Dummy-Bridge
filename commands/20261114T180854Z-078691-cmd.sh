# boxctl: timeout=300
# loop session (Max, 17:57 UTC: "We should continue collecting gen (whichever)"): this box's twelve Gen 8 self-play runs
# ended at 17:15 UTC and it stood idle. The source moves to 352c72b (sg8u1 to sg8u36 in jobs-azure1.txt, deals 800,000 on),
# the collection and the row publisher start again (the publisher with the new runs).
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; COMMIT=352c72b26f89e4f246e60fae0014c3c6613bb900
sudo systemctl stop loop-collect loop-collect-b loop-rows 2>/dev/null || true; sleep 3
git -C "$S" status --short | head -5
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo "$(date -u +%FT%TZ) Gen 8's self-play goes on (sg8u1 to sg8u36; the box was idle from 17:15; source ${COMMIT:0:7})" >> "$W/runs.log"
sudo systemctl reset-failed loop-collect loop-collect-b loop-rows 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure1.txt"
# shellcheck disable=SC2046
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$S/$T/rows.sh" sg8e $(grep -v '^#' "$S/$T/jobs-azure1.txt" | awk '{print $1}' | grep '^sg8' | tr '\n' ' ')
sleep 150; systemctl is-active loop-collect loop-rows | tr '\n' ' '; tail -n 3 "$W/runs.log" | cut -c1-170; pgrep -u "$USER" -fc scripts/x8_match.py || true; uptime | cut -c1-70; date -u +%FT%TZ
