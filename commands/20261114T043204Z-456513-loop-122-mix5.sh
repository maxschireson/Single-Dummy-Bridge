# boxctl: timeout=600
# boxctl: timeout=600
# loop session (read-only, Nice 10; Max, 04:30 UTC on 14 November: "What percent of training deals are Ben right now?"):
# rows and deals by deciding bot and by the bot on the other side, in v2's training set and in round 3's.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
ls -d "$W"/r3* "$W"/pub/train-r3 2>/dev/null | tr '\n' ' '; echo; ls -la "$W"/r3/*.npz 2>/dev/null | awk '{print $5, $9}' | head -12
cd "$S2" 2>/dev/null || cd "$W/src"
nice -n 10 "$PY" - "$HOME/work/plan/rnet2w/data/train.npz" "$W/r3/train.npz" "$W/r3/stu_train.npz" "$W/r3/replay.npz" <<'PY'
import importlib.util, sys, os
import numpy as np
spec = importlib.util.spec_from_file_location('train_rollout_net', 'scripts/train_rollout_net.py')
trainer = importlib.util.module_from_spec(spec); spec.loader.exec_module(trainer)
for path in sys.argv[1:]:
    if not os.path.exists(path):
        print(path, 'missing'); continue
    z = trainer.stored_arrays(path)
    names = [str(x) for x in np.asarray(z['bot_names'])]; cols = [str(x) for x in np.asarray(z['meta_columns'])]
    meta = np.asarray(z['meta']); deal = np.asarray(z['deal'])
    print('\n' + path, '| rows', len(deal), '| deals', len(np.unique(deal)), '| meta columns', cols)
    for col in [c for c in range(len(cols)) if 'bot' in cols[c]]:
        ids = meta[:, col].astype(np.int64)
        print('  by', cols[col])
        for b in np.argsort(-np.bincount(ids[ids >= 0], minlength=len(names))):
            n = int((ids == b).sum())
            if n:
                print('    %-14s rows %9d  %5.1f%%   deals %7d  %5.1f%%' % (names[b], n, 100 * n / len(ids), len(np.unique(deal[ids == b])), 100 * len(np.unique(deal[ids == b])) / len(np.unique(deal))))
        if (ids < 0).any(): print('    (none)         rows %9d  %5.1f%%' % (int((ids < 0).sum()), 100 * (ids < 0).mean()))
PY
date -u +%FT%TZ
