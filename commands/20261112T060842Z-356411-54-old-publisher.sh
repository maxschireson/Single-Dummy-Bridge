# boxctl: timeout=120
# The Gen 7.0 self-play cohort on this box is finished (11 boards, all published); stop its publisher, which only refreshes a heartbeat.
R=$HOME/work/runs/gen7-phase1-selfplay-capture-$BOXCTL_BOX
p=$($HOME/work/venv/bin/python -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$R/publisher-status.json"); r=$(ls "$R/receipts" | wc -l)
[ "$p" = "$r" ] || { echo "published $p of $r; left running"; exit 1; }
touch "$R/PUBLISH_STOP"; for i in $(seq 1 16); do [ "$(systemctl is-active arena-selfplay-publish)" = active ] || break; sleep 5; done
sudo systemctl disable --now arena-selfplay-publish >/dev/null 2>&1; sudo systemctl disable arena-selfplay >/dev/null 2>&1
echo "7.0 self-play cohort: $r boards published; publisher $(systemctl is-active arena-selfplay-publish)"
echo "== go71b"; tail -12 $HOME/work/gen71/go71b.log | cut -c1-520
echo "== memory"; free -m | awk 'NR==2{print "available " $7 " MB"}'; ps -eo rss,args --no-headers --sort=-rss | grep "[m]ultiprocessing.spawn" | head -8 | awk '{printf "%d MB  ", $1/1024}'; echo
