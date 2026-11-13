# boxctl: timeout=60
nproc; free -g | head -2; uptime; W=$HOME/work/x8; grep -o "\"source[^,]*" $W/runs/x1/manifest.json | head -3; grep -c . $W/runs/x1/results.jsonl; grep x1 $W/queue.log | tail -3
