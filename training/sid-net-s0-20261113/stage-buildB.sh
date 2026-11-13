# Stage `buildB` of chain.sh (sourced): the held-out set (boards after v2's tips), labels in full with floors, deals
# of the training set dropped.
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/gen7_build_dataset.py --episodes "$W/epsB" --scorer "$SCORER" --policy-only \
  --labels "$W/labelsB" --label-floors --out "$W/data/freshB_raw.npz" --workers "$WORKERS" > "$W/logs/buildB.log" 2>&1 || stop "build B failed: $(tail -2 "$W/logs/buildB.log" | cut -c1-300)"
"$PY" $T/fresh_set.py "$W/data/freshB_raw.npz" "$W/data/freshB.npz" "$W/data/train.npz" > "$W/logs/freshB.log" 2>&1 || stop "fresh B failed: $(tail -2 "$W/logs/freshB.log" | cut -c1-300)"
log "freshB: $(cat "$W/logs/freshB.log")"
rm -f "$W/data/freshB_raw.npz"
