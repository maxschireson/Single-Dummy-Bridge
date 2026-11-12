# boxctl: timeout=30
# boxctl: timeout=30
# g8: why did the tuning unit stop?
G=$HOME/work/g8; tail -n 25 "$G/est/tune-all.log" | cut -c1-300; journalctl -u g8-tune-all --no-pager -n 6 2>/dev/null | cut -c1-200; free -m | head -2
