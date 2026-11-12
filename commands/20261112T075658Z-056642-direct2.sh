# boxctl: timeout=60
#!/bin/bash
P=$HOME/work/p41; S=$HOME/work/p41src
sudo systemctl stop p41-direct.service
cat > $P/direct.sh <<'EOS'
#!/bin/bash
P=$HOME/work/p41; S=$HOME/work/p41src; PY=$HOME/work/venv/bin/python
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
cd $S
{
echo "== v4.1 (512 wide, three epochs) against 768 wide, five epochs, directly: every fresh set but B"
$PY scripts/gen7_compare_nets.py $P/data/freshALL_F.npz 1 0 w512=$P/runs/w512/policy_epoch3_T.npz w768e5=$P/runs/w768e5/policy_epoch5_T.npz > $P/logs/direct_all.txt 2>&1; head -4 $P/logs/direct_all.txt
echo "== the same on B"
$PY scripts/gen7_compare_nets.py $P/data/freshB.npz 1 0 w512=$P/runs/w512/policy_epoch3_T.npz w768e5=$P/runs/w768e5/policy_epoch5_T.npz > $P/logs/direct_b.txt 2>&1; head -4 $P/logs/direct_b.txt
} > $P/logs/eval_direct.log 2>&1
echo "direct comparison done $(date -u +%T)" >> $P/logs/timeline.log
EOS
sudo systemd-run --unit=p41-direct2 --uid="$(id -un)" --working-directory="$S" --setenv=HOME="$HOME" -- /bin/bash $P/direct.sh 2>&1 | tail -1
