# boxctl: timeout=30
date -u +%T; tail -n 14 $HOME/work/gen8/prepnext8.log | cut -c1-230; for u in prepnext8 next8 arena-gen8 gen8-recycle; do printf '%s=%s ' $u "$(systemctl is-active $u)"; done; echo
tail -2 $HOME/work/gen8/next8.log 2>/dev/null | cut -c1-200
