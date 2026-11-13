# boxctl: timeout=300
# boxctl: timeout=300
# loop session (read-only): rows by table kind (0 root, 1 tie fork, 2 gap fork) in round 3a's pure-Stu rows on azure5,
# and the capture settings the collection's bots record with.
W=$HOME/work/loop; PY=$W/venv/bin/python
nice -n 10 "$PY" - <<'PY'
import numpy as np, os, json
W = os.path.expanduser('~/work/loop')
z = np.load(f'{W}/r3a/stu_train.npz', allow_pickle=True)
meta, deal = z['meta'], z['deal']
k, n = np.unique(meta[:, 2], return_counts=True)
print('rows', len(meta), 'tables', len(np.unique(deal)), '| by kind', dict(zip(k.tolist(), n.tolist())), '| searched', int((meta[:, 10] == 1).sum()))
b = json.load(open(f'{W}/src/configs/loop-bots.json'))
for name in ('stu0-pa', 'stu0-pra', 'stu0a'):
    print(name, 'capture', b[name]['x8'].get('capture'))
PY
