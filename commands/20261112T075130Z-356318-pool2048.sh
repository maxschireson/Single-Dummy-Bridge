# boxctl: timeout=100
#!/bin/bash
W=$HOME/work; G=$W/g8p41; P=$W/p41
for s in 4 5 6 7; do sudo systemctl stop g8-reading-$s.service; done
echo "reading bench: shards 4-7 stopped, their cores go to a pool-2048 run $(date -u +%T)" >> $P/logs/timeline.log
cat > $P/reading2048.sh <<'EOS'
#!/bin/bash
# reading2048.sh SHARD SECONDS : the same bench with a pool of 2048 before the deal list, four nets
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; M=$G/models/cardplay
cd $G
export BRIDGE_DDS_CACHE= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
$PY scripts/gen8_reading_bench.py pools --episodes $P/epsB --episodes $P/epsC --episodes $P/epsD --episodes $P/epsE --skip-families $P/data/gen7_v41_train.npz \
  --out $P/runs/reading2048 --shard $1/8 --seconds $2 --part 2 --pool 2048 \
  --net v0=$M/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz --net v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz \
  --net v4.1=$M/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz --net e5=$P/runs/w512e5/policy_epoch5_T.npz > $P/logs/reading2048-$1.out 2>&1
echo "reading2048 shard $1 exit $? $(date -u +%T)" >> $P/logs/timeline.log
EOS
chmod +x $P/reading2048.sh
for s in 4 5 6 7; do
  sudo systemd-run --unit=g8-reading2048-$s --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" --nice=5 -- /bin/bash $P/reading2048.sh $s 5400 >/dev/null 2>&1
done
sleep 5; systemctl list-units --no-legend "g8-*" | cut -c1-70; cat $P/runs/reading/pools-0?.log | grep -c table; date -u +%T
ps -eo etimes,pcpu,args | grep compare_nets | grep -v grep | cut -c1-90; cat $P/logs/eval_direct.log | cut -c1-300
