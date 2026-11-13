# boxctl: timeout=120
# boxctl: timeout=120
# loop session: tables so far and the last hour's rate per collection run (read-only).
W=$HOME/work/loop; now=$(date +%s)
for r in sp0 spr0 sp0b spr0b sp0c spr0c; do
  E=$W/runs/$r/episodes; [ -d "$E" ] || continue
  n=$(ls "$E" | wc -l); h=$(find "$E" -name '*.json.gz' -mmin -60 | wc -l); q=$(find "$E" -name '*.json.gz' -mmin -20 | wc -l)
  echo "$r $n tables | last 60 min $h | last 20 min $q"
done
systemctl is-active loop-collect loop-collect-b loop-chain 2>/dev/null | tr '\n' ' '; uptime | sed 's/.*load/load/'; date -u +%FT%TZ
