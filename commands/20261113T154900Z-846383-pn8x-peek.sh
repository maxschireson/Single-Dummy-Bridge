# boxctl: timeout=30
date -u +%T; tail -n 6 $HOME/work/gen8x/prepnext8x.log | cut -c1-220; for u in prepnext8x next8x arena-gen8x; do printf '%s=%s ' $u "$(systemctl is-active $u)"; done; echo; tail -1 $HOME/work/gen8x/next8x.log 2>/dev/null | cut -c1-160
