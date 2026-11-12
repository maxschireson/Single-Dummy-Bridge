# boxctl: timeout=60
# p41 found on azure5 (board, 06:31 UTC) that Ubuntu's daily unattended upgrade restarts running units through needrestart,
# transient units included. This sets needrestart to list such services instead of restarting them (the same one-line file p41
# wrote on azure5), and reports when the upgrade timer last ran and whether any collector unit was stopped by it today.
set -uo pipefail
F=/etc/needrestart/conf.d/50-list-only.conf
if [ -d /etc/needrestart/conf.d ]; then
  [ -e "$F" ] && echo "already set: $(cat $F)" || { echo "\$nrconf{restart} = 'l';" | sudo tee "$F" >/dev/null; echo "written: $(cat $F)"; }
else
  echo "needrestart is not installed here (no /etc/needrestart/conf.d)"
fi
echo "timers: $(systemctl list-timers --all --no-pager 2>/dev/null | grep -E "apt-daily" | awk '{print $(NF-1)": next "$1" "$2" "$3", last "$6" "$7" "$8}' | tr '\n' ';' | cut -c1-300)"
echo "unattended upgrades today: $(grep -c "^$(date -u +%F).*Packages that will be upgraded" /var/log/unattended-upgrades/unattended-upgrades.log 2>/dev/null) run(s) with packages; last lines:"
grep "^$(date -u +%F)" /var/log/unattended-upgrades/unattended-upgrades.log 2>/dev/null | tail -3 | cut -c1-220
echo "needrestart restarts today (journal):"
sudo journalctl --since today --no-pager 2>/dev/null | grep -i -E "needrestart|Restarting services" | tail -4 | cut -c1-200
echo "units stopped today:"
for u in $(systemctl list-units --all --no-legend --plain 'arena-*' 'ben-server@*' 'lane-recycle*' 'gen71-recycle*' 'go71*' 'switch71*' 'g8-*' 2>/dev/null | awk '{print $1}'); do
  n=$(sudo journalctl -u "$u" --since today --no-pager 2>/dev/null | grep -c "Stopping "); [ "$n" -gt 0 ] && echo "   $u: stopped $n time(s), last $(sudo journalctl -u "$u" --since today --no-pager | grep "Stopping " | tail -1 | cut -c1-16)"
done; echo "(end)"
