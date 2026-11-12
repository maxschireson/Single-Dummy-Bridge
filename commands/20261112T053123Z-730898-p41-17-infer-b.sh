# boxctl: timeout=300
# p41: validation of the net's reading of the play (layout weights from trick 7): scripts/gen7_check.py inference with v4 and with 4.1
# on the same fresh tables (deals the training set does not have), at the lowest CPU priority beside the training runs.
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
cd $S && git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git show FETCH_HEAD:scripts/gen7_check.py > scripts/gen7_check.py && grep -c "split >= 0" scripts/gen7_check.py; sudo systemctl reset-failed "p41-inf-*" 2>/dev/null
rm -rf $P/epsV; mkdir -p $P/epsV/s0 $P/epsV/s1 $P/runs/infer
$PY - <<'PY'
import gzip, os, re
from pathlib import Path
import numpy as np
P = Path.home() / 'work/p41'
keep = set()
for n in ('B', 'C', 'D'):
    with np.load(P / f'data/fresh{n}.npz') as z:
        keep.update(z['family'].tolist())
pat = re.compile(r'"family":\s*"([^"]+)"')
files = []
for d in ('epsB', 'epsC', 'epsD'):
    for f in sorted((P / d).glob('*.json.gz')):
        with gzip.open(f, 'rt') as g:
            m = pat.search(g.read(20000))
        if m is None:
            import json
            with gzip.open(f, 'rt') as g:
                fam = json.load(g)['family']
        else:
            fam = m.group(1)
        if fam in keep:
            files.append(f)
files.sort(key=lambda f: f.name)
for i, f in enumerate(files):
    os.symlink(f, P / 'epsV' / f's{i % 2}' / f.name)
print(len(files), 'episodes on deals the training set does not have, in 2 shards')
PY
for s in 0 1; do for n in v4 v41; do
  pol=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz; [ $n = v41 ] && pol=$P/runs/w512/policy_epoch3_T.npz
  sudo systemd-run --unit=p41-inf-$n-$s --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --nice=19 -- /bin/bash -c "$PY scripts/gen7_check.py inference --episodes $P/epsV/s$s --split -1 --tables 100000 --seconds 4200 --policy $pol --out $P/runs/infer/${n}_s$s.json > $P/logs/inf_${n}_s$s.log 2>&1; echo \"inf $n s$s exit \$? \$(date -u +%T)\" >> $P/logs/timeline.log" 2>&1 | tail -1
done; done
sleep 20; ps -eo pcpu,ni,etimes,args --sort=-pcpu | grep "gen7_check\|train_gen7" | grep -v grep | awk '{print $1, $2, $3, $5, $6, $7, $14, $15, $16}' | cut -c1-120; tail -3 $P/logs/timeline.log; tail -1 $P/logs/w512e5.err; tail -1 $P/logs/w768e5.err; grep -c . $P/logs/eval768.log
