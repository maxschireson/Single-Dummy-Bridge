# boxctl: timeout=100
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41; M=$G/models/cardplay
cd $G && git fetch -q --depth=1 origin feature/gen8-p41-20261112 && git show FETCH_HEAD:scripts/gen8_reading_bench.py > scripts/gen8_reading_bench.py
for s in 4 5 6 7; do sudo systemctl stop g8-reading2048-$s.service; done
ls $P/runs/reading2048/*.npz 2>/dev/null | wc -l; cat $P/runs/reading2048/pools-0?.log 2>/dev/null | tail -4
echo "pool-2048 run stopped (pool size turned out not to matter before the deal list); shards 4-7 of the bench continue $(date -u +%T)" >> $P/logs/timeline.log
cat > $P/reading_more.sh <<'EOS'
#!/bin/bash
# reading_more.sh SHARD SECONDS : continue a shard of the bench after its last complete part file
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; M=$G/models/cardplay
cd $G
export BRIDGE_DDS_CACHE= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
parts=$(ls $P/runs/reading/pools-0$1-*.npz 2>/dev/null | wc -l)
$PY scripts/gen8_reading_bench.py pools --episodes $P/epsB --episodes $P/epsC --episodes $P/epsD --episodes $P/epsE --skip-families $P/data/gen7_v41_train.npz \
  --out $P/runs/reading --shard $1/8 --seconds $2 --part 4 --skip-tables $((4 * parts)) --part-offset $parts \
  --net v0=$M/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz --net v2=$M/gen7-policy-v2-2026-11-11/gen7_policy_v2.npz \
  --net v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz --net v4.1=$M/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz \
  --net e5=$P/runs/w512e5/policy_epoch5_T.npz > $P/logs/reading-$1.more.out 2>&1
echo "reading shard $1 (continued) exit $? $(date -u +%T)" >> $P/logs/timeline.log
EOS
chmod +x $P/reading_more.sh
for s in 4 5 6 7; do
  sudo systemd-run --unit=g8-readingm-$s --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" --nice=5 -- /bin/bash $P/reading_more.sh $s 1900 >/dev/null 2>&1
done
sleep 20; systemctl list-units --no-legend "g8-*" | cut -c1-70; for s in 4 5; do ls $P/runs/reading/pools-0$s-*.npz | wc -l; tail -1 $P/runs/reading/pools-0$s.log; done; date -u +%T
cat $P/logs/eval_direct.log | cut -c1-300
