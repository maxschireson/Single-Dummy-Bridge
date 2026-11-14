# boxctl: timeout=60
# boxctl: timeout=60
# loop session (read-only): when the collections ran on this box, for their rates.
W=$HOME/work/loop
grep -E "start (sg8e|sp3se|sp3s |sp3sb|sp3sc|sp3sd)|paused|ended; back|moves to" "$W/runs.log" | tail -n 14 | cut -c1-140
for r in sg8e sp3se sp3s sp3sb sp3sc sp3sd; do f=$W/runs/$r/results.jsonl; [ -e $f ] && echo "$r $(wc -l < $f) tables; first row $(date -u -r $W/runs/$r/manifest.json +%H:%M 2>/dev/null) last $(date -u -r $f +%H:%M)"; done
