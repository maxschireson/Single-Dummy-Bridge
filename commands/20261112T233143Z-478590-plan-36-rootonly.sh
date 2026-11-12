# boxctl: timeout=260
# boxctl: timeout=180
# plan session: azure5: stop match4 at 721+ boards (prc-32-v41 is 0.107 +- 0.042 IMPs a board behind match1 on the same deals);
# run match6 = prr-32-v41 (claim finder at the root only, playouts unchanged) against 7s-32-v41 on match1's deals, then match5.
set -uo pipefail
P=$HOME/work/plan
python3 - <<'PY'
import os
p = os.path.expanduser('~/work/plan/queue.txt')
pos = int(open(os.path.expanduser('~/work/plan/queue.pos')).read())
lines = open(p).read().splitlines()
done, waiting = lines[:pos + 1], lines[pos + 1:]
assert done[-1].split()[0] == 'match4', done[-1][:40]
m6 = done[-1].replace('match4 ', 'match6 ', 1).replace('prc-32-v41~', 'prr-32-v41~')
out = [m6] + waiting
tmp = p + '.new'
open(tmp, 'w').write('\n'.join(done + out) + '\n')
os.replace(tmp, p)
print('waiting now:', ' '.join(l.split()[0] for l in out))
PY
pkill -f "pair prc-32-v41~7s-32-v41" || echo "nothing to stop"
sleep 45
echo "position $(cat "$P/queue.pos")"; tail -3 "$P/queue.log" | cut -c1-170; tail -1 "$P/runs/match6.log" 2>/dev/null | cut -c1-120; wc -l < "$P/runs/match4/results.jsonl"
