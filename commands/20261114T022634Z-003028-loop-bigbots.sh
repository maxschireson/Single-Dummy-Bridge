# boxctl: timeout=600
# boxctl: timeout=600
# loop session (read-only, Nice 10): rows by bot in rollout net v2's training set (the plan session's set on azure5), for
# Max's experiment (01:26 PT): a net from the strongest bots' data against one from the present mix, the same size.
W=$HOME/work/loop; PY=$W/venv/bin/python
ls -la $HOME/work/plan/rnet2w/data/ 2>&1 | head
nice -n 10 "$PY" - <<'PY'
import numpy as np, os, zipfile
p = os.path.expanduser('~/work/plan/rnet2w/data/train.npz')
z = np.load(p, mmap_mode='r', allow_pickle=True)
names = [str(x) for x in z['bot_names']]
meta = z['meta']
print('rows', meta.shape[0], 'deals', len(z['family']) if 'family' in z.files else '?')
own = np.asarray(meta[:, 8]); gap = np.asarray(meta[:, 10])
c = np.bincount(own, minlength=len(names)); g = np.bincount(own, weights=gap, minlength=len(names))
for i in np.argsort(-c):
    if c[i]: print(f'{names[i]:>10} {int(c[i]):>10} rows, {int(g[i]):>10} with the search gap')
PY
