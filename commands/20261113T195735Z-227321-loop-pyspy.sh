# boxctl: timeout=900
# boxctl: timeout=900
# loop session: where a live collection worker's time goes (py-spy samples one pure-Stu worker of sp0 for 120 s; read-only
# for the collection, which keeps running).
set -uo pipefail
W=$HOME/work/loop; PY=$W/venv/bin/python
"$W/venv/bin/pip" install -q py-spy 2>&1 | tail -1
P=$(pgrep -f "x8_match.py.*stu0-pa~stu0-pb" | head -1)
C=$(pgrep -P "$P" | head -1)
echo "chain worker parent $P child $C: $(ps -o pcpu=,etimes=,cmd= -p "$C" | cut -c1-120)"
sudo "$W/venv/bin/py-spy" record -p "$C" -d 120 -r 100 --format raw -o /tmp/spy.txt --nonblocking > /tmp/spy.log 2>&1 || tail -3 /tmp/spy.log
"$PY" - <<'PY'
import collections, re
incl, self_ = collections.Counter(), collections.Counter(); total = 0
for line in open('/tmp/spy.txt'):
    stack, _, n = line.rstrip().rpartition(' ')
    n = int(n); total += n
    frames = stack.split(';')
    names = []
    for f in frames:
        m = re.match(r'(.*) \((.*):(\d+)\)', f)
        names.append(f'{m.group(1)} ({m.group(2).split("/")[-1]})' if m else f)
    for name in set(names):
        incl[name] += n
    self_[names[-1]] += n
print('samples', total)
print('inclusive (top 40):')
for k, v in incl.most_common(40): print(f'  {100 * v / total:5.1f}%  {k[:110]}')
print('self (top 25):')
for k, v in self_.most_common(25): print(f'  {100 * v / total:5.1f}%  {k[:110]}')
PY
date -u +%FT%TZ
