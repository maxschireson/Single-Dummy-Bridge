# boxctl: timeout=200
#!/bin/bash
set -uo pipefail
P=$HOME/work/p41; S=$HOME/work/p41src
cd $S
git fetch -q --depth 1 origin transfer/gen7-policy-v4.1-20261112 && git show FETCH_HEAD:scripts/gen7_near_tie.py > scripts/gen7_near_tie.py
cat > $P/neartie_src.sh <<'EOS'
#!/bin/bash
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python; M=$HOME/work/repo/models/cardplay
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
cd $S
tests=(); for n in B C D E; do tests+=(--test $P/data/fresh${n}_raw.npz $P/data/pairs$n.npz); done
for b in 2 0; do for s in 1 0; do
  $PY scripts/gen7_near_tie.py --net v4.1=$P/runs/w512/policy_epoch3_T.npz --net v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz --bot $b --source $s --min-pairs 150 \
    --head v4.1=all=$P/runs/result_head_final/result_head.npz "${tests[@]}" --drop $P/data/gen7_v41_train.npz --out $P/runs/neartie/near_tie_bot${b}_source$s.json > $P/logs/neartie_bot${b}_source$s.log 2>&1
  echo "neartie bot $b source $s exit $? $(date -u +%T)" >> $P/logs/timeline.log
done; done
# which bots are behind bot code 2, and what the audits of Gen 7 runs look like
$PY - > $P/logs/neartie_bots.log 2>&1 <<'PYEOF'
import gzip, json, glob, collections, os
P = os.path.expanduser('~/work/p41')
bots, kinds = collections.Counter(), collections.Counter()
for d in ('epsB', 'epsC', 'epsD', 'epsE'):
    for f in sorted(glob.glob(f'{P}/{d}/*.json.gz'))[:400]:
        e = json.load(gzip.open(f, 'rt'))
        bots[(e['candidate'], e['opponent'])] += 1
        for t in e['unique_tables'].values():
            for x in t.get('audits') or []:
                kinds[(e['candidate'], x.get('kind') or x.get('type') or x.get('reason') or ','.join(sorted(k for k in x if k not in ('ply',)))[:150])] += 1
print(bots.most_common(12))
for k, v in kinds.most_common(12): print(v, k)
PYEOF
bash $P/pushnt.sh
EOS
sudo systemctl reset-failed p41-neartie-bots 2>/dev/null
sudo systemd-run --unit=p41-neartie-src --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" --nice=19 -- /bin/bash $P/neartie_src.sh 2>&1 | tail -1
sleep 100
tail -5 $P/logs/timeline.log; cat $P/logs/neartie_bots.log | cut -c1-900; tail -c 100 $P/logs/w768e5.err
