# boxctl: timeout=120
# boxctl: timeout=120
# g8: Max, 06:03 UTC: "we can keep this one indefinitely also" (Bridgebots6). Cancel the timer that would have
# deallocated it at 09:55 UTC. The unit files stay, disabled, for whoever stops the box one day.
set -uo pipefail
sudo systemctl disable --now g8-azure6-stop.timer 2>&1 | tail -1
sudo systemctl stop g8-azure6-deallocate.timer 2>/dev/null
systemctl list-timers 'g8-*' 'azure5-*' --all --no-pager 2>/dev/null | sed -n 1,5p | cut -c1-120
systemctl is-enabled g8-azure6-stop.timer 2>&1 | sed 's/^/g8-azure6-stop.timer: /'
