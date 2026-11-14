grep "^{\"epoch\": 1" $HOME/work/loop/exp-width/w1536.log | cut -c1-420; $HOME/work/loop/venv/bin/python -c "
import numpy as np
for name, p in ((\"w1536\", \"$HOME/work/loop/exp-width/w1536/policy_epoch1.npz\"), (\"v2\", \"$HOME/work/loop/src-lc/models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz\")):
    z = np.load(p, allow_pickle=True)
    n = sum(z[k].size for k in z.files if z[k].dtype.kind == \"f\")
    big = sorted(((z[k].size, k, z[k].shape) for k in z.files if z[k].dtype.kind == \"f\"), reverse=True)[:4]
    print(name, \"float parameters\", n, big)
"
