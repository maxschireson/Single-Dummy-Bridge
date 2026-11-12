# boxctl: timeout=120
# p41: Ubuntu's daily unattended upgrade restarted the running 768-wide training unit at 06:23:48 UTC (needrestart restarts services
# whose libraries were upgraded, transient units included). Make needrestart list such services instead of restarting them on this box.
set -uo pipefail
echo "\$nrconf{restart} = 'l';" | sudo tee /etc/needrestart/conf.d/50-list-only.conf >/dev/null
cat /etc/needrestart/conf.d/50-list-only.conf; sudo needrestart -b 2>/dev/null | head -5
P=$HOME/work/p41; echo "w768e5 was restarted by the daily unattended upgrade at 06:23:48 (needrestart); it runs again from the start. needrestart set to list-only $(date -u +%T)" >> $P/logs/timeline.log
tail -2 $P/logs/w768e5.err; systemctl is-active p41-w768e5 p41-eval-w768e5
