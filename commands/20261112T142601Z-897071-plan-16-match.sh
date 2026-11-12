# boxctl: timeout=300
# boxctl: timeout=120
# plan session: a played test on azure2: Gen 7.1 with the bot as its own simulator at tricks 7 to 12, against Gen 7.1.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
by = {l.split()[0]: l for l in waiting}
new = {
 'match1': 'match1 $PY scripts/plan_match.py --source $HOME/work/capsule-gen7-capture/recovery --bots configs/plan-bots.json --pair pr75-32-v41~7s-32-v41 --deals 1600 --seed 131 --workers 8 --out $R',
 'ceil64b': 'ceil64b $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 64 --max-gap 0.25 --skip-files 500 --files 500 --workers 8 --out $R.json',
}
order = ['@source', 'match1', 'ceil64b', 'matrix1', 'fam1', 'matrix2']
out = []
for name in order:
    if name == '@source':
        out.append('@source b839df0e178bb2bfca014c686c92581813a8910e')
    elif name in new:
        out.append(new[name])
    elif name in by:
        out.append(by[name])
    else:
        raise SystemExit(f'{name} is not waiting: nothing changed')
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] if not l.startswith('@') else '@source' for l in out))
PY
echo "position $(cat "$P/queue.pos"); $(tail -1 "$P/queue.log" | cut -c1-90)"; tail -1 "$P/runs/rb1.log" | cut -c1-100; ls $HOME/work/capsule-gen7-capture/recovery | head -5
