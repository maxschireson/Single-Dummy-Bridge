# Stage `e1` of chain.sh (sourced): the student against the solver on the held-out boards (E1 of the specification),
# rollout net v2 beside it on the same rows; and what the label runs cost and hold.
"$PY" scripts/sid_e1.py --data "$W/data/freshB.npz" --net "$W/s0/policy.npz" --net "$V2" --out "$W/e1" > "$W/logs/e1.log" 2>&1 \
  || stop "E1 failed: $(tail -2 "$W/logs/e1.log" | cut -c1-300)"
log "e1: $(head -1 "$W/e1/e1.txt")"
"$PY" experiments/sid_loop/label_stats.py "$W/labels" --json "$W/data/label_stats.json" > "$W/logs/label_stats.txt" 2>&1 || log "label stats failed"
"$PY" experiments/sid_loop/label_stats.py "$W/labelsB" --json "$W/data/labelB_stats.json" > "$W/logs/labelB_stats.txt" 2>&1 || log "label B stats failed"
