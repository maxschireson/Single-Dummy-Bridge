# boxctl: timeout=120
# boxctl: timeout=120
# loop session: what is on the box before taking it for the collection (read-only).
nproc; free -g | sed -n 2p; df -h ~ | tail -1; uptime | sed 's/.*load/load/'
ls ~/work | tr '\n' ' '; echo
systemctl list-units --type=service --state=running --no-legend 2>/dev/null | grep -v "systemd\|ssh\|cron\|dbus\|getty\|network\|polkit\|rsyslog\|snap\|unattended\|udisks\|walinux\|chrony\|multipath\|hv-\|irqbalance\|ModemManager\|packagekit\|user@\|fwupd" | cut -c1-120 | head -14
systemctl list-timers --no-legend 2>/dev/null | grep -v "systemd\|apt\|logrotate\|man-db\|fstrim\|motd\|e2scrub\|fwupd\|sysstat\|update-notifier\|dpkg" | cut -c1-140 | head -8
ls -d ~/work/capsule*/recovery ~/work/plan/capsule/recovery 2>/dev/null
ls ~/work/runs 2>/dev/null | tail -8 | tr '\n' ' '; echo
for r in ~/work/runs/gen8-x3-azure1*; do [ -d "$r" ] && { echo "$r: $(ls "$r" | tr '\n' ' ' | cut -c1-300)"; ls "$r/episodes" 2>/dev/null | wc -l; cat "$r/state.json" 2>/dev/null | head -c 400; echo; }; done
ps -eo pcpu,etimes,cmd --sort=-pcpu | head -6 | cut -c1-150
