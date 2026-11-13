# boxctl: timeout=30
date -u +%T; tail -n 12 $HOME/work/gen8x/go8x.log | cut -c1-260; for u in go8x arena-gen8x arena-gen8x-publish gen8x-recycle sidplay; do printf '%s=%s ' $u "$(systemctl is-active $u)"; done; echo
