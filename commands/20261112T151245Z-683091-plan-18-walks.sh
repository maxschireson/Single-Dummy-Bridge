# boxctl: timeout=300
# boxctl: timeout=120
# plan session: on azure5, the posterior of the bot-as-model reading by tempered walks, after the trick 1-2 ceiling.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
by = {l.split()[0]: l for l in waiting}
M = 'models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz'
new = {
 'rbc2': f'rbc2 $PY scripts/plan_reading_bound.py --episodes $P/data/fresh_g6sp --net {M} --trick 6 --files 30 --skip-files 300 --chain 400 --chains 2 --workers 8 --out $R.json',
 'rbc1': f'rbc1 $PY scripts/plan_reading_bound.py --episodes $P/data/fresh_g6sp --net {M} --trick 6 --files 40 --skip-files 300 --chain 600 --chains 2 --inner-samples 8 --inner-list 32 --table 0.872,0.043,0.071,0.071,0.071,0.021,0.007,0.001,0.0005 --workers 8 --out $R.json',
}
order = [n for n in ['rbs5', 'rbs3', 'ceilT12', '@source', 'rbc2', 'rbc1', 'wide3', 'ceil16c'] if n in by or n in new or n == '@source']
out = []
for name in order:
    if name == '@source':
        out.append('@source 2a3a4111f4e28c9d838ad8e658c6e0b9c7854633')
    elif name in new:
        out.append(new[name])
    else:
        out.append(by[name])
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in out))
PY
echo "position $(cat "$P/queue.pos"); $(tail -1 "$P/queue.log" | cut -c1-80)"
