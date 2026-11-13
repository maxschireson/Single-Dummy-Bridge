# Stage `train` of chain.sh (sourced): S_0 = rollout net v2 plus the label heads, --init from v2, v2's recipe.
unset OMP_NUM_THREADS OPENBLAS_NUM_THREADS MKL_NUM_THREADS
if ! PYTHONPATH=$W/pylib "$PY" -c "import jax, optax" 2>/dev/null; then
  "$PY" -m pip install -q --target "$W/pylib" "jax[cpu]" optax > "$W/logs/pip.log" 2>&1 || stop "pip install failed"
fi
[ -f "$V2" ] || stop "no net to start from at $V2"
log "S_0 start from $(basename "$V2") (lr $LR, $EPOCHS epochs, width $WIDTH)"
PYTHONPATH=$W/pylib "$PY" scripts/train_rollout_net.py --data "$W/data/train.npz" --all-train --val-data "$W/data/freshB.npz" \
  --kind suit --width "$WIDTH" --epochs "$EPOCHS" --lr "$LR" --init "$V2" --id-dropout 0.15 --save-epochs --out "$W/s0" --compare "$V2" \
  > "$W/logs/s0.out" 2> "$W/logs/s0.err" || stop "S_0 FAILED: $(tail -2 "$W/logs/s0.err" | cut -c1-400)"
log "S_0 done: $(tail -1 "$W/logs/s0.out" | cut -c1-400)"
