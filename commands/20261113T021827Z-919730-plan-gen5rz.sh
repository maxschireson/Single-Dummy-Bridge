# boxctl: timeout=240
# boxctl: timeout=240
# plan session: azure5: add the Gen 5RZ feeds (arena-gen5rz*, 8,523 boards; Max 02:15) to the rollout net v2 run: stop its
# chain and resume it at 7caad4f (keeps the built parts or the joined set; the new boards become one more part).
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'rnet2wr', done[-1][:60]
assert not any(l.split()[:1] == ['rnet2wr2'] for l in lines), 'already queued'
cmd = done[-1].split(' ', 1)[1]
job = 'rnet2wr2 ' + ('' if cmd.startswith('RESUME=1') else 'RESUME=1 ') + cmd
out = ['@source 7caad4f197f23f27279d06d825b3eae4b2060d15', job] + waiting
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('waiting now:', ' | '.join(l[:70] for l in out))
PY
tail -2 $P/rnet2w/logs/timeline.log | cut -c1-120
pkill -f "rollout-net-v2-20261113/chain.sh" ; pkill -f "gen7_build_dataset.py --episodes $P/rnet2w" ; pkill -f "merge_sets.py $P/rnet2w" ; pkill -f "train_rollout_net.py --data $P/rnet2w"
sleep 5
cd $P/rnet2w && for f in shards/s*.npz; do [ -f "$f" ] || continue; $HOME/work/venv/bin/python -c "import numpy as np,sys; z=np.load(sys.argv[1]); [z[k].shape for k in ('meta','deal','family','bot_names')]" "$f" 2>/dev/null || { echo "removing incomplete $f"; rm -f "$f"; }; done
ls shards 2>/dev/null | tr '\n' ' '; echo; ls -la data | awk '{print $5, $9}' | tail -8
sleep 60
echo "position $(cat $P/queue.pos)"; tail -2 $P/queue.log | cut -c1-150; tail -4 $P/rnet2w/logs/timeline.log | cut -c1-200
