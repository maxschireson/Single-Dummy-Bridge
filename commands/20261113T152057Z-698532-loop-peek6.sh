# boxctl: timeout=120
# boxctl: timeout=120
# loop session: what azure6 has, before setting up ~/work/loop there (read-only).
nproc; free -g | sed -n 2p; df -h ~ | tail -1; uptime | sed 's/.*load/load/'
ls ~/work | tr '\n' ' '; echo
systemctl list-units --type=service --state=running --no-legend 2>/dev/null | grep -v "systemd\|ssh\|cron\|dbus\|getty\|network\|polkit\|rsyslog\|snap\|unattended\|udisks\|walinux\|chrony\|multipath\|hv-\|irqbalance\|ModemManager\|packagekit\|user@" | cut -c1-110 | head -12
find ~/work -maxdepth 4 -name manifest.json -path '*recovery*' 2>/dev/null | head -8
find ~/work -maxdepth 3 -name 'sure_cpp' 2>/dev/null | head -5
ls ~/work/venv/bin/python ~/work/sidnet/venv/bin/python 2>/dev/null
ls ~/work/sidnet 2>/dev/null | head -20 | tr '\n' ' '; echo
for d in ~/work/sidnet/capsule ~/work/x8/capsule ~/work/capsule*; do [ -e "$d" ] && { echo "$d: $(ls "$d" | head -5 | tr '\n' ' ')"; }; done
ps -eo pcpu,etimes,cmd --sort=-pcpu | head -5 | cut -c1-140
python3 --version; g++ --version | head -1; ls ~/.ssh/boxctl_github 2>/dev/null
