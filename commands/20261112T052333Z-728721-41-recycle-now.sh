# boxctl: timeout=780
# The collectors' worker processes on the BEN lanes grow by about 24 MB a board (2.4 to 2.7 GB each after about 105 boards) and the
# box is nearly out of memory. Restart every lane's collector the graceful way: STOP, let the board in hand finish, start the same
# unchanged cohort again. BEN servers and publishers are left running. Nothing is deleted.
W=$HOME/work; . "$W/lanes/role.env"
run() { echo "$W/runs/gen7-phase1-$BOX-$LABEL-$1"; }
echo "$(date -u +%T) before: $(free -m | awk 'NR==2{print "available " $7 " MB"}'); boards $(cat $W/runs/gen7-phase1-$BOX-$LABEL-*/state.json | grep -o '"completed": [0-9]*' | awk '{s+=$2} END {print s}')"
for n in 1 2 3 4 5 6 7 8; do touch "$(run $n)/STOP"; done
for i in $(seq 1 120); do
  active=0; for n in 1 2 3 4 5 6 7 8; do [ "$(systemctl is-active arena-ben@$n)" = active ] && active=$((active+1)); done
  [ "$active" -eq 0 ] && break; sleep 5
done
echo "$(date -u +%T) collectors still running after the wait: $active"
for n in 1 2 3 4 5 6 7 8; do
  R=$(run $n); state=$(systemctl is-active arena-ben@$n)
  if [ -n "$(ls "$R/failures")" ]; then echo "lane $n: FAILURE record $(ls "$R/failures" | tr '\n' ' '); left stopped"; continue; fi
  if [ "$state" = active ]; then echo "lane $n: still finishing a board; STOP left in place"; continue; fi
  rm -f "$R/STOP"; sudo systemctl reset-failed arena-ben@$n 2>/dev/null; sudo systemctl start arena-ben@$n
done
sleep 45
echo "$(date -u +%T) after: $(free -m | awk 'NR==2{print "available " $7 " MB"}')"
for n in 1 2 3 4 5 6 7 8; do echo -n "lane $n: collector $(systemctl is-active arena-ben@$n), server $(systemctl is-active ben-server@$n), boards $(ls "$(run $n)/receipts" | wc -l), STOP $([ -e "$(run $n)/STOP" ] && echo yes || echo no); "; done; echo
tail -2 "$W/lanes/1.collector.log" | cut -c1-200
