# boxctl: timeout=60
W=$HOME/work/loop; cat $W/pub/train-r4c/stu_test.npz.sha256
$W/venv/bin/python - $W/pub/train-r4c/stu_test.npz <<'PY'
import numpy as np, sys
z = np.load(sys.argv[1]); k = list(z.keys()); print(len(z[k[0]]), 'rows;', k)
for name in ('deal', 'deal_id', 'family', 'board'):
    if name in z: print(name, len(set(map(str, z[name].tolist()))), 'distinct')
PY
