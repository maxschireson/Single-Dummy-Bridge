# boxctl: timeout=120
# The Gen 7.1 collector's workers on this box grow slowly (about 85 MB a minute over the eight of them at 06:18 UTC, cause
# not known). This installs a supervisor, unit gen71-recycle: when the box has little memory left, the collector under the
# unit arena-gen71 is restarted the graceful way (STOP, the boards in hand finish, the same unchanged cohort starts again).
# A STOP written by anyone else is respected, and the file ~/work/gen71/RECYCLE_OFF switches the supervisor off (write it
# before stopping the cohort for good).
set -euo pipefail
W=$HOME/work; S=$W/gen71
cat > "$S/recycle71.sh" <<'SH'
#!/usr/bin/env bash
set -uo pipefail
W=$HOME/work; S=$W/gen71
LIMIT=${LIMIT:-5000}
say() { echo "$(date -u +%FT%TZ) $*"; }
run_dir() { systemctl show -p ExecStart --value arena-gen71 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1; }
avail() { awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo; }
tree_mb() { local pid; pid=$(systemctl show -p MainPID --value arena-gen71); [ "${pid:-0}" != 0 ] || { echo 0; return; }; ps -o rss= --pid "$pid" --ppid "$pid" 2>/dev/null | awk '{s+=$1} END {printf "%d", s/1024}'; }
say "started: the collector is restarted after the boards in hand when the box has under $LIMIT MB of memory available"
while true; do
  sleep 30
  [ -e "$S/RECYCLE_OFF" ] && continue
  [ "$(systemctl is-active arena-gen71)" = active ] || continue
  R=$(run_dir); [ -n "$R" ] && [ -d "$R" ] || continue
  [ -e "$R/STOP" ] && continue
  a=$(avail); [ "$a" -lt "$LIMIT" ] || continue
  t=$(tree_mb)
  if [ "$t" -lt 8000 ]; then say "only $a MB available but the collector holds $t MB; not restarting it"; sleep 600; continue; fi
  say "$a MB available, collector and workers at $t MB; restarting it after the boards in hand ($(basename "$R"))"
  touch "$S/recycling"; touch "$R/STOP"
  for i in $(seq 1 360); do [ "$(systemctl is-active arena-gen71)" = active ] || break; sleep 5; done
  if [ "$(systemctl is-active arena-gen71)" = active ]; then say "did not stop in 30 minutes; STOP left in place"; rm -f "$S/recycling"; continue; fi
  if [ -n "$(ls "$R/failures" 2>/dev/null)" ]; then say "failure record $(ls "$R/failures" | tr '\n' ' '); left stopped for inspection"; rm -f "$S/recycling"; continue; fi
  if [ -e "$S/RECYCLE_OFF" ]; then say "switched off meanwhile; left stopped"; rm -f "$S/recycling"; continue; fi
  rm -f "$R/STOP"; sudo systemctl reset-failed arena-gen71 2>/dev/null; sudo systemctl start arena-gen71
  rm -f "$S/recycling"
  say "restarted with $(ls "$R/receipts" | wc -l) boards done"
done
SH
chmod +x "$S/recycle71.sh"
sudo tee /etc/systemd/system/gen71-recycle.service >/dev/null <<UNIT
[Unit]
Description=Restart the Gen 7.1 collector gracefully when the box runs short of memory

[Service]
User=$(id -un)
Environment=HOME=$HOME LIMIT=5000
ExecStart=$S/recycle71.sh
StandardOutput=append:$S/recycle71.log
StandardError=append:$S/recycle71.log
Restart=always
RestartSec=20

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now gen71-recycle >/dev/null 2>&1
sleep 40
pid=$(systemctl show -p MainPID --value arena-gen71)
echo "$(date -u +%T) gen71-recycle: $(systemctl is-active gen71-recycle); the run it would act on: $(systemctl show -p ExecStart --value arena-gen71 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1 | sed "s|$HOME|~|")"
echo "available $(awk '/^MemAvailable:/ {print int($2/1024)}' /proc/meminfo) MB; collector tree $(ps -o rss= --pid $pid --ppid $pid | awk '{s+=$1} END {printf "%d", s/1024}') MB; collector $(systemctl is-active arena-gen71); boards $(ls $W/runs/gen71-vs70-azure2/receipts | wc -l)"
tail -3 "$S/recycle71.log" | cut -c1-200
