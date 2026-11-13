# loop session: read-only look at azure3 before its lanes are drained (Max, 08:23 UTC: "Take azure 3 and 5")
SKIP='systemd-|dbus|cron|ssh|getty|polkit|rsyslog|snapd|unattended|udisks|ModemManager|networkd|multipathd|chrony|walinuxagent|hv-|boxctl|user@|irqbalance|accounts|packagekit|fwupd|serial-getty'
echo "== running units"; systemctl list-units --type=service --state=running --no-legend --no-pager | grep -v -E "$SKIP" | cut -c1-170
echo "== timers"; systemctl list-timers --all --no-legend --no-pager | grep -v -E "systemd|apt|fstrim|logrotate|man-db|motd|e2scrub|dpkg|update-notifier|fwupd|snapd|sysstat|plocate|ua-timer" | cut -c1-190
echo "== ~/work"; ls ~/work
echo "== ~/work/lanes"; ls -la ~/work/lanes | head -70
echo "== scripts that recycle or switch lanes"; for f in ~/work/lanes/*.sh ~/work/lanes/*.py; do [ -f "$f" ] && echo "--- $f ($(wc -l < "$f") lines)"; done
echo "== unit files"; ls /etc/systemd/system | grep -i -E "lane|ben|gen8|recycle|switch|fsw" | head -40
echo "== processes"; ps -eo pid,ppid,etimes,pcpu,rss,args --sort=-pcpu | grep -v "ps -eo" | head -30 | cut -c1-260
echo "== box"; nproc; free -g | sed -n 2p; df -h ~ | tail -1; uptime
