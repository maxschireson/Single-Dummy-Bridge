# Stage `buildB` of chain.sh (sourced): the held-out set (boards after v2's tips), labels in full with floors, deals
# of the training set dropped.
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "$PY" scripts/gen7_build_dataset.py --episodes "$W/epsB" --scorer "$SCORER" --policy-only \
  --labels "$W/labelsB" --label-floors --out "$W/data/freshB_raw.npz" --workers "$WORKERS" > "$W/logs/buildB.log" 2>&1 || stop "build B failed: $(tail -2 "$W/logs/buildB.log" | cut -c1-300)"
"$PY" $T/fresh_set.py "$W/data/freshB_raw.npz" "$W/data/freshB.npz" "$W/data/train.npz" > "$W/logs/freshB.log" 2>&1 || stop "fresh B failed: $(tail -2 "$W/logs/freshB.log" | cut -c1-300)"
log "freshB: $(cat "$W/logs/freshB.log")"
rm -f "$W/data/freshB_raw.npz"
"$PY" - "$W/data/freshB.npz" "$W/data/freshB_val.npz" "$VALDEALS" > "$W/logs/freshB_val.log" 2>&1 <<'PYS' || stop "the trainer's held-out part failed"
import json, sys
import numpy as np
src, out, deals = sys.argv[1], sys.argv[2], int(sys.argv[3])
with np.load(src) as z:
    d = {k: z[k] for k in z.files}
rows = d['deal'] < deals                      # the first deals in file order (episode blob ids: no order in time or feed)
o = {k: (v[rows] if len(v) == len(rows) and k not in ('family', 'deal_split') else v) for k, v in d.items()}
o['family'], o['deal_split'] = d['family'][:deals], d['deal_split'][:deals]
np.savez(out, **o)
print(json.dumps(dict(deals=int(min(deals, len(d['family']))), examples=int(rows.sum()), of_deals=int(len(d['family'])), of_examples=int(len(rows)))))
PYS
log "freshB_val: $(cat "$W/logs/freshB_val.log")"
