# boxctl: timeout=150
# Read-only: where the Gen 7.1 workers on this box spend their time. CPU share per worker over 30 s, process states sampled
# 60 times, what sleeping workers wait on (wchan), system CPU split, and a Python stack of two workers (py-spy, installed in a
# throwaway venv under /tmp; nothing in the run's venv changes).
set -uo pipefail
date -u +%H:%M:%S
pid=$(systemctl show -p MainPID --value arena-gen71)
kids=$(ps -o pid= --ppid $pid | tr -d ' ' | tr '\n' ' ')
work=$(for k in $kids; do [ "$(ps -o rss= -p $k)" -gt 200000 ] && echo $k; done | tr '\n' ' ')
echo "collector $pid; workers: $work"
tick=$(getconf CLK_TCK)
cpu() { awk '{print $14+$15}' /proc/$1/stat; }
declare -A a; for w in $work $pid; do a[$w]=$(cpu $w); done
t0=$(date +%s.%N); vm0=$(head -1 /proc/stat)
declare -A st
for i in $(seq 1 60); do for w in $work; do s=$(awk '{print $3}' /proc/$w/stat); st[$w]+=$s; done; sleep 0.5; done
t1=$(date +%s.%N); vm1=$(head -1 /proc/stat)
el=$(echo "$t1 - $t0" | bc)
tot=0
for w in $work; do d=$(( $(cpu $w) - ${a[$w]} )); p=$(echo "scale=0; 100*$d/$tick/$el" | bc); tot=$((tot+p)); s=${st[$w]}; echo "worker $w: cpu ${p}%  states R=$(echo -n $s | tr -cd R | wc -c) S=$(echo -n $s | tr -cd S | wc -c) D=$(echo -n $s | tr -cd D | wc -c) of 60"; done
echo "all workers: ${tot}% of 800%; collector main process: $(echo "scale=0; 100*($(cpu $pid) - ${a[$pid]})/$tick/$el" | bc)%"
echo "$vm0" "$vm1" | awk '{u=$13-$2; n=$14-$3; s=$15-$4; i=$16-$5; w=$17-$6; t=u+n+s+i+w+($18-$7)+($19-$8); printf "system cpu: user %.0f%%, sys %.0f%%, idle %.0f%%, iowait %.1f%%\n", 100*(u+n)/t, 100*s/t, 100*i/t, 100*w/t}'
echo "== what sleeping workers wait on (wchan, 40 samples each)"
for w in $work; do for i in $(seq 1 40); do s=$(awk '{print $3}' /proc/$w/stat); [ "$s" != R ] && cat /proc/$w/wchan && echo; sleep 0.05; done; done | sort | uniq -c | sort -rn | head -6
echo "== threads per worker and their states"
w1=$(echo $work | awk '{print $1}'); for t in /proc/$w1/task/*; do echo -n "$(basename $t):$(awk '{print $3}' $t/stat):$(cat $t/comm) "; done; echo
echo "== files the workers hold open (count by kind)"
sudo ls -l /proc/$w1/fd 2>/dev/null | awk '{print $NF}' | sed -E 's#.*/(dds-cache\.sqlite[^/]*)$#\1#; s#^/.*\.(so|npz|keras|py)[^/]*$#lib-or-model#' | sort | uniq -c | sort -rn | head -6
echo "== py-spy"
if [ ! -x /tmp/pyspy/bin/py-spy ]; then python3 -m venv /tmp/pyspy >/dev/null 2>&1 && /tmp/pyspy/bin/pip install -q py-spy >/dev/null 2>&1; fi
if [ -x /tmp/pyspy/bin/py-spy ]; then
  for w in $(echo $work | awk '{print $1, $2}'); do
    echo "-- worker $w, 10 s of samples (top functions by own time)"
    sudo timeout 30 /tmp/pyspy/bin/py-spy record --pid $w --duration 10 --rate 50 --nonblocking --format raw --output /tmp/pyspy-$w.txt >/dev/null 2>&1
    python3 - /tmp/pyspy-$w.txt <<'PY'
import sys, collections
own = collections.Counter(); total = 0; idle = 0; incl = collections.Counter()
for line in open(sys.argv[1]):
    line = line.rstrip('\n')
    if not line: continue
    stack, n = line.rsplit(' ', 1); n = int(n); total += n
    frames = stack.split(';')
    own[frames[-1][:110]] += n
    seen = set()
    for f in frames:
        k = f.split(' (')[0][:60]
        if k not in seen: incl[k] += n; seen.add(k)
print(f'   samples {total}')
for f, n in own.most_common(9): print(f'   own {100*n/total:5.1f}%  {f}')
for k in ('execute', 'commit', 'connect', 'cache', 'solve', 'lookup', 'store', 'get', 'put'):
    hits = [(kk, n) for kk, n in incl.items() if k in kk.lower()]
    for kk, n in sorted(hits, key=lambda x: -x[1])[:2]: print(f'   incl {100*n/total:5.1f}%  {kk}')
PY
  done
else
  echo "py-spy could not be installed"
fi
