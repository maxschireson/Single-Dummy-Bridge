# boxctl: timeout=60
#!/bin/bash
P=$HOME/work/p41; S=$HOME/work/p41src
cat > $P/direct.sh <<'EOS'
#!/bin/bash
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python
while ! grep -q "eval w768e5 done" $P/logs/timeline.log; do sleep 3; done
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4
cd $S
{
echo "== v4.1 (512 wide, three epochs) against 768 wide, five epochs, directly: every fresh set but B"
$PY scripts/gen7_compare_nets.py $P/data/freshALL_F.npz 1 0 w512=$P/runs/w512/policy_epoch3_T.npz w768e5=$P/runs/w768e5/policy_epoch5_T.npz | head -5
echo "== the same on B"
$PY scripts/gen7_compare_nets.py $P/data/freshB.npz 1 0 w512=$P/runs/w512/policy_epoch3_T.npz w768e5=$P/runs/w768e5/policy_epoch5_T.npz | head -5
echo "== 768 wide: epoch 4 (the trainer's pick by log-loss before temperature) against epoch 5, on B"
$PY scripts/gen7_compare_nets.py $P/data/freshB.npz 1 0 e4=$P/runs/w768e5/policy_epoch4_T.npz e5=$P/runs/w768e5/policy_epoch5_T.npz | head -5
} > $P/logs/eval_direct.log 2>&1
echo "direct comparison done $(date -u +%T)" >> $P/logs/timeline.log
EOS
sudo systemd-run --unit=p41-direct --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" -- /bin/bash $P/direct.sh 2>&1 | tail -1
date -u +%T; tail -2 $P/logs/timeline.log; sed -n "55,200p" $P/logs/eval_w768e5.log | cut -c1-200 | tail -12
