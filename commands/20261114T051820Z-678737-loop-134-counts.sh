# boxctl: timeout=60
# boxctl: timeout=60
# loop session (read-only): boards banked by the collections since round 3's cut, and what the box is doing.
W=$HOME/work/loop
for r in sp3s sp3sb sp3sc sp3sd sp3se sg8e; do [ -e "$W/runs/$r/results.jsonl" ] && echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables, last $(date -u -r "$W/runs/$r/results.jsonl" +%H:%M)"; done
echo "units: $(for u in loop-collect loop-chain loop-collect-b loop-rungs loop-rungs2 loop-rungs3 loop-next loop-bensession; do s=$(systemctl is-active $u 2>/dev/null); [ "$s" = active ] && printf '%s ' $u; done)"
tail -n 1 "$W/runs.log" | cut -c1-120
