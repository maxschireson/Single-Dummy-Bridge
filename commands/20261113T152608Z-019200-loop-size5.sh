# boxctl: timeout=120
# boxctl: timeout=120
# loop session: sizes of rows and records, and the collection's totals (read-only).
W=$HOME/work/loop
ls -la "$W/r2a/stu_train.npz" "$W/r2a/stu_held.npz" | cut -c1-120
"$W/venv/bin/python" - <<'PY'
import numpy as np, os
z = np.load(os.path.expanduser('~/work/loop/r2a/stu_train.npz'), allow_pickle=True)
print({k: (z[k].shape, str(z[k].dtype)) for k in z.files})
PY
for r in sp0 spr0; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables, $(du -sm "$W/runs/$r/episodes" | cut -f1) MB of records"; done
tail -n 2 "$W/runs.log" | cut -c1-140; systemctl is-active loop-collect loop-collect-b loop-publish | tr '\n' ' '; date -u +%FT%TZ
