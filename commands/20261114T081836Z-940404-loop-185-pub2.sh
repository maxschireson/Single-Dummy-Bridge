# boxctl: timeout=60
# boxctl: timeout=60
W=$HOME/work/loop
ps -eo pid,etimes,args | grep -E "[g]it|[p]ub.sh|[s]leep 600" | cut -c1-160 | head
git -C $W/pub log -1 --format='%cd %s' --date=format:%H:%M 2>&1 | head -2; git -C $W/pub status --short 2>/dev/null | wc -l
