# boxctl: timeout=60
# boxctl: timeout=60
# g8: my result publisher on this box has nothing left to publish (my matches here have ended and their rows are on the
# transfer branch). Stop and disable it. Only g8-publish is touched; g7's units and runs are not.
echo "before: g8 units: $(systemctl list-units 'g8-*' --all --no-legend 2>/dev/null | awk '{print $1 "=" $3 "/" $4}' | tr '\n' ' ')"
sudo systemctl stop g8-publish.service 2>&1 | tail -1
sudo systemctl disable g8-publish.service 2>&1 | tail -1
echo "g8-publish: $(systemctl is-active g8-publish.service 2>/dev/null) / $(systemctl is-enabled g8-publish.service 2>/dev/null)"
echo "g8 timers: $(systemctl list-timers 'g8-*' --all --no-legend 2>/dev/null | awk '{print $(NF-1)}' | tr '\n' ' ')"
echo "g8 processes left: $(pgrep -u "$(id -un)" -f 'work/g8' -c 2>/dev/null)"
