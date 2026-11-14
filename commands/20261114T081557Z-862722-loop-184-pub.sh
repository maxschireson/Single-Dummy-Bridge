# boxctl: timeout=60
# boxctl: timeout=60
W=$HOME/work/loop
systemctl status loop-publish --no-pager 2>/dev/null | sed -n 1,4p | cut -c1-140
journalctl -u loop-publish --no-pager -n 8 2>/dev/null | cut -c1-200
ls $W/pub | head; du -sh $W/pub/usbc $W/pub/usbc-lt 2>/dev/null
