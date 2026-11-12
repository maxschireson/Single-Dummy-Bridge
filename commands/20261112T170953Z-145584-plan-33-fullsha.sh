# boxctl: timeout=200
# boxctl: timeout=120
# plan session: the waiting source line must carry the full commit id (the runner fetches by id).
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
waiting = ['@source 0f0f4f895449ccfe2fc917c73e3b503d709a9c0f' if l.startswith('@source 0f0f4f8') else l for l in waiting]
assert any(l == '@source 0f0f4f895449ccfe2fc917c73e3b503d709a9c0f' for l in waiting), waiting[:2]
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + waiting) + '\n')
os.replace(tmp, p)
print('running:', done[-1].split()[0], '| waiting now:', ' | '.join(l[:60] for l in waiting[:3]))
PY
echo "position $(cat "$P/queue.pos")"
