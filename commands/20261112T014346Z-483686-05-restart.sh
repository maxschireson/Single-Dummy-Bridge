# boxctl: timeout=300
# Restart the match with the production watchdog's thread caps (one BLAS/OpenMP/TF thread per worker).
set -uo pipefail
RUN=$HOME/work/runs/g7s-vs-g6f-01
n0=$(find "$RUN/receipts" -name '*.json' | wc -l)
echo "before restart: $n0 boards in $(( $(date +%s) - $(stat -c %Y "$RUN/manifest.json") ))s since the cohort was prepared"
sudo systemctl stop g7s-vs-g6f-01; sleep 3
pgrep -f gen5_runtime >/dev/null && { echo "collector still running"; exit 1; }
sudo systemd-run --unit=g7s-vs-g6f-01b --uid="$(id -un)" --setenv=HOME="$HOME" \
  --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1 \
  --setenv=TF_NUM_INTRAOP_THREADS=1 --setenv=TF_NUM_INTEROP_THREADS=1 --setenv=TF_CPP_MIN_LOG_LEVEL=3 \
  --working-directory="$HOME/work/sdb-gen7" -- "$HOME/work/runs/drive.sh" "$RUN" 300 8
sleep 90
uptime
for p in $(pgrep -f "multiprocessing.spawn"); do echo -n "$(ls /proc/$p/task | wc -l) "; done; echo "threads per worker"
echo "boards now: $(find "$RUN/receipts" -name '*.json' | wc -l)"
journalctl -u g7s-vs-g6f-01b --no-pager -n 2 -o cat
