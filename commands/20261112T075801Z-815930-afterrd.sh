# boxctl: timeout=60
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; S=$W/p41src
cat > $P/after_reading.sh <<'EOS'
#!/bin/bash
# When the reading bench's shards have all ended: the owner pass and the final reports, then the tree bench with v4 against v0.
W=$HOME/work; G=$W/g8p41; P=$W/p41; S=$W/p41src; PY=$W/venv/bin/python; M=$G/models/cardplay
busy() { for u in g8-reading-0 g8-reading-1 g8-reading-2 g8-reading-3 g8-readingm-4 g8-readingm-5 g8-readingm-6 g8-readingm-7; do systemctl is-active -q $u && return 0; done; return 1; }
while busy; do sleep 5; done
echo "reading bench ended $(date -u +%T)" >> $P/logs/timeline.log
# the tree with v4 and with v0 on the same fresh fork pairs (the bench of 05:04 UTC, second net v0)
T='0:plain=1;3:plain=1,breadth=3,mass=0.98,path=0.5,path_solves=3000;3:plain=1,breadth=3,mass=0.98,path=0.5,path_solves=3000,net=2'
mkdir -p $P/runs/bench_v0
( cd $S && OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 5 $PY scripts/gen7_bench.py --episodes $P/epsU --policy $W/repo/models/cardplay/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz \
    --policy2 $M/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz --tricks "$T" --from-trick 3 --to-trick 6 --pairs 1000000 --workers 7 --seconds 1500 \
    --out $P/runs/bench_v0/rows.json > $P/logs/bench_v0.log 2>&1; echo "tree bench v0 exit $? $(date -u +%T)" >> $P/logs/timeline.log ) &
bash $P/owners.sh
bash $P/report.sh t2
bash $P/pushrd.sh
wait
EOS
chmod +x $P/after_reading.sh
sudo systemd-run --unit=g8-after-reading --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" -- /bin/bash $P/after_reading.sh 2>&1 | tail -1
grep -n "policy2\|net=\|def main\|add_argument" $S/scripts/gen7_bench.py | cut -c1-200 | head -30
