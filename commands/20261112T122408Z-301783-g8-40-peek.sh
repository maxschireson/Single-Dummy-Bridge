# boxctl: timeout=30
# boxctl: timeout=30
# g8: look at the tuning log
G=$HOME/work/g8; for f in "$G"/est/tune-*.log; do echo "== $f"; tail -n 60 "$f" | cut -c1-230; done; systemctl is-active g8-tune-est g8-tune-all g8-states 2>/dev/null | tr '\n' ' '
