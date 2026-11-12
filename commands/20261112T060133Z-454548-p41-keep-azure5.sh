# boxctl: timeout=120
# p41: Max, 12 November 05:59 UTC: "You can extend this box indefinitely to support Gen 8 development once this finishes."
# Cancel the timer that would delete Bridgebots5 (azure5) at 07:35 UTC. The reaper script stays in place, unarmed, for whoever
# deletes the box later. Touches nothing else on azure1.
set -uo pipefail
systemctl list-timers azure5-reaper.timer --no-pager 2>&1 | sed -n '2p'
sudo systemctl stop azure5-reaper.timer 2>/dev/null; sudo systemctl reset-failed azure5-reaper.service azure5-reaper.timer 2>/dev/null
echo "timer after: $(systemctl is-active azure5-reaper.timer 2>/dev/null)"; systemctl list-timers --all --no-pager 2>/dev/null | grep -c "azure5-reaper"
ls -la $HOME/azure5-reaper.sh | awk '{print $1, $9}'; date -u +%T
