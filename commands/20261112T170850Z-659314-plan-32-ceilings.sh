# boxctl: timeout=200
# boxctl: timeout=120
# plan session: azure5 after the opening-lead ceiling: tricks 1 to 2 after the lead, level cards at tricks 3 to 6, the
# 64-layout check, then wider hybrid seats and the short walks. match2 moves to azure2.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'ceilLead', done[-1][:40]
by = {l.split()[0]: l for l in waiting}
c = '$PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --workers 8 --out $R.json'
new = {'@source': '@source 0f0f4f8',
       'ceilT12b': 'ceilT12b ' + c + ' --worlds 16 --from-trick 1 --to-trick 2 --skip-files 120 --files 400',
       'ceilTies': 'ceilTies ' + c + ' --worlds 16 --ties --bands=-1 --from-trick 3 --to-trick 6 --files 150',
       'ceil64b': 'ceil64b ' + c + ' --worlds 64 --max-gap 0.25 --skip-files 500 --files 300'}
order = [n for n in ['@source', 'ceilT12b', 'ceilTies', 'ceil64b', 'wide3', 'rbc2a', 'rbc2b'] if n in by or n in new]
out = [new.get(n) or by[n] for n in order]
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' '.join(l.split()[0] for l in out))
PY
cd "$P/src" && git fetch -q origin research/plan-leverage-g8-20261112 && git cat-file -t 0f0f4f8 && git log -1 --format='%h %s' 0f0f4f8 | cut -c1-90
echo "position $(cat "$P/queue.pos")"; tail -1 "$P/runs/ceilLead.log" | cut -c1-120
