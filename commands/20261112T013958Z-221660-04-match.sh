# boxctl: timeout=300
# Start the 7s-32 vs 6-32 match as its own systemd unit: 8 workers, STOP after 300 boards.
set -euo pipefail
RUN=$HOME/work/runs/g7s-vs-g6f-01
cat > "$HOME/work/runs/drive.sh" <<'SH'
#!/usr/bin/env bash
# drive.sh RUN BOARDS WORKERS: run the collector until BOARDS receipts exist, then STOP and let in-flight boards finish.
RUN=$1; N=$2; W=$3
cd "$HOME/work/sdb-gen7" || exit 1
"$HOME/work/venv/bin/python" -u ops/gen5_runtime.py --run "$RUN" --workers "$W" >> "$RUN.collector.log" 2>&1 &
pid=$!
echo "$(date -u +%FT%TZ) collector pid $pid, $W workers, STOP after $N boards"
while kill -0 "$pid" 2>/dev/null; do
  n=$(find "$RUN/receipts" -name '*.json' | wc -l)
  if [ "$n" -ge "$N" ] && [ ! -e "$RUN/STOP" ]; then touch "$RUN/STOP"; echo "$(date -u +%FT%TZ) $n boards: STOP written"; fi
  sleep 10
done
wait "$pid"; rc=$?
echo "$(date -u +%FT%TZ) collector exited with $rc after $(find "$RUN/receipts" -name '*.json' | wc -l) boards"
SH
chmod +x "$HOME/work/runs/drive.sh"
[ -e "$RUN/STOP" ] && { echo "STOP already present in $RUN"; exit 1; }
sudo systemd-run --unit=g7s-vs-g6f-01 --uid="$(id -un)" --setenv=HOME="$HOME" \
  --working-directory="$HOME/work/sdb-gen7" -- "$HOME/work/runs/drive.sh" "$RUN" 300 8
sleep 45
systemctl is-active g7s-vs-g6f-01
journalctl -u g7s-vs-g6f-01 --no-pager -n 5 -o cat
tail -3 "$RUN.collector.log"; uptime
