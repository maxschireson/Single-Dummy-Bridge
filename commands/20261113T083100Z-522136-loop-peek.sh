# loop session: read-only look at azure5 before pausing plan's queue (Max, 08:23 UTC: "Take azure 3 and 5")
SKIP='systemd-|dbus|cron|ssh|getty|polkit|rsyslog|snapd|unattended|udisks|ModemManager|networkd|multipathd|chrony|walinuxagent|hv-|boxctl|user@|irqbalance|accounts|packagekit|fwupd|serial-getty'
echo "== running units"; systemctl list-units --type=service --state=running --no-legend --no-pager | grep -v -E "$SKIP" | cut -c1-160
echo "== transient or waiting units"; systemctl list-units --type=service --all --no-legend --no-pager | grep -i -E "plan|match|rbc|p41|g8|loop|x8" | cut -c1-160
echo "== timers"; systemctl list-timers --all --no-legend --no-pager | grep -v -E "systemd|apt|fstrim|logrotate|man-db|motd|e2scrub|dpkg|update-notifier|fwupd|snapd|sysstat|plocate|ua-timer" | cut -c1-170
echo "== processes"; ps -eo pid,ppid,etimes,pcpu,rss,args --sort=-pcpu | grep -v "ps -eo" | head -24 | cut -c1-300
echo "== ~/work"; ls ~/work
echo "== ~/work/plan (newest first)"; ls -lat ~/work/plan | head -28
echo "== box"; nproc; free -g | sed -n 2p; df -h ~ | tail -1; uptime
