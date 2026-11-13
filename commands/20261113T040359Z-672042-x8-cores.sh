# boxctl: timeout=60
nproc; free -g | head -2; uptime; W=$HOME/work/x8; cat $W/runs/x1/manifest.json 2>/dev/null | head -c 600; echo; wc -l < $W/runs/x1/results.jsonl; git -C $W/src log -1 --format=%h; ps -eo pid,etime,args | grep x8_match | grep -v grep | cut -c1-150
