# boxctl: timeout=30
set -u
date -u +%T
tail -n 22 $HOME/work/gen8/go8.log | cut -c1-260
for u in go8 arena-gen8 arena-gen8-publish gen8-recycle; do printf '%s=%s ' $u "$(systemctl is-active $u 2>/dev/null)"; done; echo
R=$HOME/work/runs/gen8-$(hostname | tr A-Z a-z); ls $HOME/work/runs | grep gen8 | tr '\n' ' '; echo
ps -eo pcpu,etimes,args --sort=-pcpu | head -4 | cut -c1-160
