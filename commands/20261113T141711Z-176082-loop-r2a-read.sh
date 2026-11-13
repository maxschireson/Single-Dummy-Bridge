# boxctl: timeout=120
# boxctl: timeout=120
# loop session: read round 2's first training run (read-only).
W=$HOME/work/loop
systemctl is-active loop-collect loop-train2 | tr '\n' ' '; echo
cut -c1-230 "$W/r2a/timeline.log"; tail -n 3 "$W/r2a/net.log" 2>/dev/null | cut -c1-200; wc -l < "$W/runs/spr0/results.jsonl"; date -u +%FT%TZ
