# boxctl: timeout=120
# p41: arm the temporary box's deletion on the wall clock (07:35:00 UTC) instead of a countdown: the countdown timer had drifted
# by about 8 minutes in 1.6 hours (it showed 05:50:29 where it was armed for 05:42:45).
set -uo pipefail
sudo systemctl stop azure5-reaper.timer 2>/dev/null; sudo systemctl reset-failed azure5-reaper.service 2>/dev/null
sudo systemd-run --unit=azure5-reaper --on-calendar="2026-11-12 07:35:00 UTC" --timer-property=AccuracySec=1s --uid="$(id -un)" --setenv=HOME="$HOME" /bin/bash "$HOME/azure5-reaper.sh" 2>&1 | tail -2
systemctl list-timers azure5-reaper.timer --no-pager 2>&1 | sed -n '1,3p'; date -u +%T; timedatectl 2>/dev/null | grep -i "synchronized\|NTP" | head -2
