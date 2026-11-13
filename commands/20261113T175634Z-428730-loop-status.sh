# boxctl: timeout=120
# boxctl: timeout=120
# loop session: is the collection running again, and how far (read-only).
W=$HOME/work/loop
systemctl is-active loop-collect loop-collect-b loop-chain loop-publish loop-rows loop-rungs loop-rungs2 loop-switch loop-after-ben 2>/dev/null | tr '\n' ' '; echo "(collect collect-b chain publish rows rungs rungs2 switch after-ben)"
for r in sp0 spr0 sp0b spr0b sp0c spr0c; do [ -f "$W/runs/$r/results.jsonl" ] && echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables"; done
tail -n 4 "$W/runs.log" | cut -c1-150; cat "$W/rows.log" 2>/dev/null | tail -3 | cut -c1-200; ls -la "$W/pub/rows" 2>/dev/null | tail -4 | cut -c1-110
uptime | sed 's/.*load/load/'; df -h "$W" | tail -1; date -u +%FT%TZ
