# boxctl: timeout=300
# boxctl: timeout=300
set -u
echo "== host"; hostname; nproc; free -g | sed -n 2p; uptime
echo "== work"; ls ~/work 2>&1 | head -40
for d in ~/work/sdb-gen8 ~/work/g8; do echo "== $d"; [ -d "$d" ] && (git -C "$d" log --oneline -1 2>&1; git -C "$d" status -sb 2>&1 | head -3; ls "$d" | head -30); done
echo "== venvs"; ls -d ~/work/venv* ~/work/*/venv* 2>/dev/null; for v in ~/work/venv ~/work/sdb-gen8/.venv; do [ -x "$v/bin/python" ] && "$v/bin/python" -c "import sys, numpy; print(sys.version.split()[0], numpy.__version__)"; done
echo "== dds"; ls -la ~/work/sdb-gen8/bridge_harness/libbridge_dds.so 2>&1
echo "== models"; ls ~/work/sdb-gen8/models/cardplay 2>&1 | head -30; ls -la ~/work/sdb-gen8/models/cardplay/gen7-policy-v4.1-2026-11-12/ 2>&1 | head
echo "== runs"; ls ~/work/runs 2>&1 | head
echo "== units"; systemctl list-units --type=service --state=running --no-pager 2>/dev/null | grep -v -E "systemd|dbus|ssh|cron|getty|rsyslog|polkit|udisks|snapd|chrony|hv_|walinux|unattended|multipathd|networkd|resolved|logind|journald|udevd|irqbalance|ModemManager" | head -15
