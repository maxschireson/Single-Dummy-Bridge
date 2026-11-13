# boxctl: timeout=240
# boxctl: timeout=240
# plan session: azure5: the v2 warm start missed the two arena-gen71-* feeds (5,482 Gen 7.1 boards; azure2's run has
# them). Stop the chain before it trains, and resume it at bc8524160b5ae833ea3cc1f6eb55d290b85171ad: keep its fetch and built parts, fetch the gen71 feeds
# (and whatever arrived), build them as one more part, join, then train as before (Max, 02:05).
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'rnet2w', done[-1][:60]
assert not any(l.split()[:1] == ['rnet2wr'] for l in lines), 'already queued'
job = 'rnet2wr RESUME=1 ' + done[-1].split(' ', 1)[1]
out = ['@source bc8524160b5ae833ea3cc1f6eb55d290b85171ad', job] + waiting
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('waiting now:', ' | '.join(l[:70] for l in out))
PY
tail -3 $P/rnet2w/logs/timeline.log | cut -c1-120
pkill -f "rollout-net-v2-20261113/chain.sh" ; pkill -f "gen7_build_dataset.py --episodes $P/rnet2w" ; pkill -f "merge_sets.py $P/rnet2w" ; pkill -f "train_rollout_net.py --data $P/rnet2w"
sleep 5
cd $P/rnet2w && for f in shards/s*.npz; do [ -f "$f" ] || continue; $HOME/work/venv/bin/python -c "import numpy as np,sys; z=np.load(sys.argv[1]); [z[k].shape for k in ('meta','deal','family','bot_names')]" "$f" 2>/dev/null || { echo "removing incomplete $f"; rm -f "$f"; }; done
ls $P/rnet2w/shards | tr '\n' ' '; echo
sleep 45
echo "position $(cat $P/queue.pos)"; tail -2 $P/queue.log | cut -c1-150; tail -4 $P/rnet2w/logs/timeline.log | cut -c1-200
