# boxctl: timeout=120
# The collector of a BEN lane grows by about 24 MB a board in its worker process (seen on azure2 and azure3; the BEN servers do not
# grow). This installs a small supervisor, unit lane-recycle: when a lane's collector is over the limit it is restarted the graceful
# way (STOP, the board in hand finishes, the same unchanged cohort starts again), one lane at a time. A STOP written by anyone else
# is respected, and the file ~/work/lanes/RECYCLE_OFF switches the supervisor off (write it before stopping lanes for good).
set -euo pipefail
W=$HOME/work; L=$W/lanes
cat > "$L/recycle.sh" <<'SH'
#!/usr/bin/env bash
set -uo pipefail
W=$HOME/work; L=$W/lanes; . "$L/role.env"
LIMIT=${LIMIT:-1900}
say() { echo "$(date -u +%FT%TZ) $*"; }
tree_mb() { local pid; pid=$(systemctl show -p MainPID --value "arena-ben@$1"); [ "${pid:-0}" != 0 ] || { echo 0; return; }; ps -o rss= --pid "$pid" --ppid "$pid" 2>/dev/null | awk '{s+=$1} END {printf "%d", s/1024}'; }
say "started: limit $LIMIT MB a lane (collector and its workers)"
while true; do
  for n in 1 2 3 4 5 6 7 8; do
    [ -e "$L/RECYCLE_OFF" ] && break
    R=$W/runs/gen7-phase1-$BOX-$LABEL-$n
    [ -e "$R/STOP" ] && continue
    [ "$(systemctl is-active "arena-ben@$n")" = active ] || continue
    mb=$(tree_mb "$n"); [ "$mb" -gt "$LIMIT" ] || continue
    say "lane $n: collector at $mb MB; restarting it after the board in hand"
    touch "$L/$n.recycling"; touch "$R/STOP"
    for i in $(seq 1 240); do [ "$(systemctl is-active "arena-ben@$n")" = active ] || break; sleep 5; done
    if [ "$(systemctl is-active "arena-ben@$n")" = active ]; then say "lane $n: did not stop in 20 minutes; STOP left in place"; rm -f "$L/$n.recycling"; continue; fi
    if [ -n "$(ls "$R/failures" 2>/dev/null)" ]; then say "lane $n: failure record $(ls "$R/failures" | tr '\n' ' '); left stopped for inspection"; rm -f "$L/$n.recycling"; continue; fi
    if [ -e "$L/RECYCLE_OFF" ]; then say "lane $n: switched off meanwhile; left stopped"; rm -f "$L/$n.recycling"; continue; fi
    rm -f "$R/STOP"; sudo systemctl reset-failed "arena-ben@$n" 2>/dev/null; sudo systemctl start "arena-ben@$n"
    rm -f "$L/$n.recycling"
    say "lane $n: restarted with $(ls "$R/receipts" | wc -l) boards done"
  done
  sleep 30
done
SH
chmod +x "$L/recycle.sh"
sudo tee /etc/systemd/system/lane-recycle.service >/dev/null <<UNIT
[Unit]
Description=Restart a BEN lane's collector gracefully when its memory passes a limit

[Service]
User=$(id -un)
Environment=HOME=$HOME LIMIT=1900
ExecStart=$L/recycle.sh
StandardOutput=append:$L/recycle.log
StandardError=append:$L/recycle.log
Restart=always
RestartSec=20

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now lane-recycle >/dev/null 2>&1
sleep 50
echo "lane-recycle: $(systemctl is-active lane-recycle); $(free -m | awk 'NR==2{print "available " $7 " MB"}')"
. "$L/role.env"
for n in 1 2 3 4 5 6 7 8; do pid=$(systemctl show -p MainPID --value arena-ben@$n); echo -n "lane $n: $(ps -o rss= --pid $pid --ppid $pid 2>/dev/null | awk '{s+=$1} END {printf "%d MB", s/1024}') $(systemctl is-active arena-ben@$n); "; done; echo
tail -6 "$L/recycle.log" | cut -c1-200
