# boxctl: timeout=60
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; S=$W/p41src
sudo systemctl stop g8-after-reading2.service
cat > $P/after_reading3.sh <<'EOS'
#!/bin/bash
# When the reading bench's shards have all ended: the owner pass and the final reports; beside them two tree benches on the
# same fresh fork pairs: (A) the launched tree with v4 and with v0; then (B) the launched tree with v4 on 32 layouts in place of 8.
W=$HOME/work; G=$W/g8p41; P=$W/p41; S=$W/p41src; PY=$W/venv/bin/python; M=$G/models/cardplay
busy() { for u in g8-reading-0 g8-reading-1 g8-reading-2 g8-reading-3 g8-readingm-4 g8-readingm-5 g8-readingm-6 g8-readingm-7; do systemctl is-active -q $u && return 0; done; return 1; }
while busy; do sleep 5; done
echo "reading bench ended $(date -u +%T)" >> $P/logs/timeline.log
L='plain=1,breadth=3,mass=0.98,path=0.5,path_solves=3000'
V4=$W/repo/models/cardplay/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz
mkdir -p $P/runs/bench_v0 $P/runs/bench_l32
( cd $S; export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
  nice -n 5 $PY scripts/gen7_bench.py --episodes $P/epsU --policy $V4 --policy2 $M/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz \
    --tricks "0:plain=1;3:$L;3:$L,net=2" --from-trick 3 --to-trick 6 --pairs 1000000 --workers 7 --seconds 1560 \
    --out $P/runs/bench_v0/rows.json > $P/logs/bench_v0.log 2>&1; echo "tree bench A (v4 and v0) exit $? $(date -u +%T)" >> $P/logs/timeline.log
  nice -n 5 $PY scripts/gen7_bench.py --episodes $P/epsU --policy $V4 --layouts 32 \
    --tricks "0:plain=1;3:$L" --from-trick 3 --to-trick 6 --pairs 1000000 --workers 8 --seconds 2700 \
    --out $P/runs/bench_l32/rows.json > $P/logs/bench_l32.log 2>&1; echo "tree bench B (32 layouts) exit $? $(date -u +%T)" >> $P/logs/timeline.log ) &
bash $P/owners.sh
bash $P/report.sh t2
bash $P/pushrd.sh
wait
EOS
chmod +x $P/after_reading3.sh
sudo systemd-run --unit=g8-after-reading3 --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" -- /bin/bash $P/after_reading3.sh 2>&1 | tail -1
date -u +%T; cat $P/logs/eval_direct.log | cut -c1-330 | tail -5; tail -1 $P/logs/timeline.log
