# boxctl: timeout=300
# p41: tree bench on fresh fork pairs (boards no net has trained on): the launched Gen 7 tree with v4 and with 4.1 on the same pairs.
# Episodes: sets B and C, only deals the training set does not have. Runs as unit p41-bench, time-boxed to end by 05:31 UTC.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
rm -rf $P/epsU; mkdir -p $P/epsU $P/runs/bench
$PY - <<'PY'
import gzip, json, os, re
from pathlib import Path
import numpy as np
P = Path.home() / 'work/p41'
keep = set()
for n in ('B', 'C'):
    with np.load(P / f'data/fresh{n}.npz') as z:
        keep.update(z['family'].tolist())
who, kept, total = {}, 0, 0
pat = {k: re.compile(r'"%s": "([^"]+)"' % k) for k in ('family', 'candidate', 'opponent')}
for d in ('epsB', 'epsC'):
    for f in sorted((P / d).glob('*.json.gz')):
        total += 1
        with gzip.open(f, 'rt') as g:
            head = g.read(6000)
        m = {k: p.search(head) for k, p in pat.items()}
        if not all(m.values()):
            with gzip.open(f, 'rt') as g:
                e = json.load(g)
            fam, cand, opp = e['family'], e['candidate'], e['opponent']
        else:
            fam, cand, opp = (m[k].group(1) for k in ('family', 'candidate', 'opponent'))
        if fam in keep:
            who[fam] = [cand, opp]
            os.symlink(f, P / 'epsU' / f.name)
            kept += 1
json.dump(who, open(P / 'runs/bench/bots.json', 'w'))
import collections
print(total, 'fresh episodes,', kept, 'on deals the training set does not have;', dict(collections.Counter('~'.join(v) for v in who.values()).most_common(8)))
PY
SECS=$(( $(date -u -d "today 05:31:00" +%s) - $(date -u +%s) )); echo "bench budget $SECS s"
T='0:plain=1;3:plain=1,breadth=3,mass=0.98,path=0.5,path_solves=3000;3:plain=1,breadth=3,mass=0.98,path=0.5,path_solves=3000,net=2'
echo "bench start $(date -u +%T)" >> $P/logs/timeline.log
sudo systemd-run --unit=p41-bench --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 -- /bin/bash -c "
  $PY scripts/gen7_bench.py --episodes $P/epsU --policy $M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz --policy2 $P/runs/w512/policy_epoch3_T.npz \
    --tricks '$T' --from-trick 3 --to-trick 6 --pairs 1000000 --workers 5 --seconds $SECS --out $P/runs/bench/rows.json > $P/logs/bench.log 2>&1; echo \"bench exit \$? \$(date -u +%T)\" >> $P/logs/timeline.log" 2>&1 | tail -1
sleep 40; echo "--- bench.log"; tail -5 $P/logs/bench.log | cut -c1-300; ps -eo pcpu,etimes,args --sort=-pcpu | grep "gen7_bench" | grep -v grep | head -3 | cut -c1-90; tail -4 $P/logs/timeline.log
