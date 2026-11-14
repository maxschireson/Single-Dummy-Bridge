W=$HOME/work/loop; tail -n 4 $W/runs.log | cut -c1-160; grep -v Warning $W/pub/exp/seat-bu3.err | tail -n 3 | cut -c1-200; wc -l < $W/pub/exp/seat-bu3.jsonl; head -c 4200 $W/pub/exp/seat-bu3.txt
