# boxctl: timeout=300
# boxctl: timeout=300
# g8: the queue asked nproc for the worker count, and nproc answers 1 when OMP_NUM_THREADS=1 is set (as it is for this
# unit, to keep each worker's linear algebra single-threaded). Ask for all processors instead; the running job resumes.
set -uo pipefail
G=$HOME/work/g8
sed -i 's/--workers "\$(nproc)"/--workers "$(nproc --all)"/' "$G/queue.sh"
grep -c 'nproc --all' "$G/queue.sh"
sudo systemctl restart g8-queue
sleep 45
tail -2 "$G/queue.log" | cut -c1-170
tail -1 "$G"/runs/x1-*.log | cut -c1-200
uptime | sed 's/.*load/load/'
