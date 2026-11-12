# boxctl: timeout=120
# p41: Max extended the temporary training box until 07:42 UTC (12 November, 05:25 UTC). Move its deletion timer to 07:35 UTC.
# Touches nothing else on azure1.
set -uo pipefail
systemctl list-timers azure5-reaper.timer --no-pager 2>&1 | sed -n '2p'
sudo systemctl stop azure5-reaper.timer 2>/dev/null; sudo systemctl reset-failed azure5-reaper.service 2>/dev/null
SECS=$(( $(date -u -d "today 07:35:00" +%s) - $(date -u +%s) )); echo "new timer in $SECS s"
[ "$SECS" -gt 600 ] || { echo "target time is not in the future; nothing armed"; exit 1; }
sudo systemd-run --unit=azure5-reaper --on-active=$SECS --uid="$(id -un)" --setenv=HOME="$HOME" /bin/bash "$HOME/azure5-reaper.sh" 2>&1 | tail -2
systemctl list-timers azure5-reaper.timer --no-pager 2>&1 | sed -n '1,3p'
test -x $HOME/azure5-reaper.sh && echo "reaper script present"; date -u +%T
