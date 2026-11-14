W=$HOME/work/loop; echo "bench: $(systemctl is-active loop-seatbench); decisions: $(wc -l < $W/pub/exp/seat-bu3.jsonl)"; grep -v Warning $W/pub/exp/seat-bu3.err | tail -n 2 | cut -c1-160; date -u +%T
