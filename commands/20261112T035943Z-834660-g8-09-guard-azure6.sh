# boxctl: timeout=300
# boxctl: timeout=300
# g8: the Azure auto-shutdown schedule could not be set (resource provider Microsoft.DevTestLab is not registered and
# this identity may not register it). Replace the transient timer with a persistent one that survives a reboot of
# azure1: Bridgebots6 is deallocated at 09:55 UTC today, inside the 6 hours Max allowed (created 03:58 UTC).
set -uo pipefail
U=$(id -un)
sudo tee /etc/systemd/system/g8-azure6-stop.service >/dev/null <<UNIT
[Unit]
Description=g8: deallocate Bridgebots6 (6-hour limit set by Max, 12 Nov)
[Service]
Type=oneshot
User=$U
Environment=HOME=$HOME
ExecStart=/bin/bash -lc 'az login --identity --output none && az vm deallocate -g Bridgebots_group -n Bridgebots6'
UNIT
sudo tee /etc/systemd/system/g8-azure6-stop.timer >/dev/null <<UNIT
[Unit]
Description=g8: deallocate Bridgebots6 at 09:55 UTC on 12 Nov 2026
[Timer]
OnCalendar=2026-11-12 09:55:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now g8-azure6-stop.timer 2>&1 | tail -1
sudo systemctl stop g8-azure6-deallocate.timer 2>/dev/null
systemctl list-timers 'g8-*' --no-pager 2>/dev/null | sed -n 1,4p | cut -c1-120
