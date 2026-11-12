# boxctl: timeout=300
#!/bin/bash
# Gen 8 Task 1: set up the prototype source at my branch and start the reading bench when the 768-wide run has ended.
set -uo pipefail
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python
[ -d $G/.git ] || { git init -q $G; git -C $G remote add origin https://github.com/maxschireson/Single-Dummy-Bridge; }
cd $G && git fetch -q --depth=1 origin feature/gen8-p41-20261112 && git checkout -q -f FETCH_HEAD && git log -1 --format='source %h %s' | cut -c1-110
for m in gen7-policy-v0-2026-11-11 gen7-policy-v2-2026-11-11 gen7-policy-v4-2026-11-11 gen7-policy-v4.1-2026-11-12 hand-fit-scorer-v0-2026-11-11; do
  (cd models/cardplay/$m && [ -e $(ls *.part000 | sed 's/.part000//') ] || $PY restore.py >/dev/null); done
[ -e models/cardplay/gen5-2026-11-10/policy.npz ] || $PY models/cardplay/gen5-2026-11-10/restore_policy.py >/dev/null
ls -la models/cardplay/*/*.npz | awk '{print $5, $9}'
if [ ! -e bridge_harness/libbridge_dds.so ]; then
  so=$(ls $W/p41src/bridge_harness/libbridge_dds.so $W/repo/bridge_harness/libbridge_dds.so 2>/dev/null | head -1)
  if [ -n "$so" ]; then cp $so bridge_harness/; else $PY scripts/build_dds.py 2>&1 | tail -1; fi
fi
ls -la bridge_harness/libbridge_dds.so | awk '{print $5, $9}'
sha256sum $P/runs/w512e5/policy_epoch5_T.npz models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz $P/runs/w512/policy_epoch3_T.npz | cut -c1-110
mkdir -p $P/runs/reading $P/logs
cat > $P/reading.sh <<'EOS'
#!/bin/bash
# reading.sh SHARD SECONDS : one shard of the bench
W=$HOME/work; G=$W/g8p41; P=$W/p41; PY=$W/venv/bin/python; M=$G/models/cardplay
cd $G
export BRIDGE_DDS_CACHE= OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
$PY scripts/gen8_reading_bench.py pools --episodes $P/epsB --episodes $P/epsC --episodes $P/epsD --episodes $P/epsE --skip-families $P/data/gen7_v41_train.npz \
  --out $P/runs/reading --shard $1/8 --seconds $2 --part 4 \
  --net v0=$M/gen7-policy-v0-2026-11-11/gen7_policy_v0.npz --net v2=$M/gen7-policy-v2-2026-11-11/gen7_policy_v2.npz \
  --net v4=$M/gen7-policy-v4-2026-11-11/gen7_policy_v4.npz --net v4.1=$M/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz \
  --net e5=$P/runs/w512e5/policy_epoch5_T.npz > $P/logs/reading-$1.out 2>&1
echo "reading shard $1 exit $? $(date -u +%T)" >> $P/logs/timeline.log
EOS
cat > $P/reading_start.sh <<'EOS'
#!/bin/bash
P=$HOME/work/p41; G=$HOME/work/g8p41
while ! grep -q "w768e5 exit" $P/logs/timeline.log; do sleep 5; done
echo "reading bench starts $(date -u +%T)" >> $P/logs/timeline.log
for s in 0 1 2 3 4 5 6 7; do
  sudo systemd-run --unit=g8-reading-$s --uid="$(id -un)" --working-directory="$G" --setenv=HOME="$HOME" --nice=5 -- /bin/bash $P/reading.sh $s 4500 >/dev/null 2>&1
done
EOS
chmod +x $P/reading.sh $P/reading_start.sh
grep -n "w768e5 exit" $P/train_w768e5.sh $HOME/work/p41src/training/policy-v4.1-20261112/*.sh 2>/dev/null | head -3
systemctl cat p41-w768e5 2>/dev/null | grep ExecStart | cut -c1-900
