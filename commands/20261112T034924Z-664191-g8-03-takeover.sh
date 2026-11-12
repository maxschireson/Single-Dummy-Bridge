# boxctl: timeout=1200
# boxctl: timeout=1200
# g8 (Gen 8 chat) takes this box for Gen 8 experiments. Max's instructions of 12 Nov 02:38 and 02:45 UTC;
# notice to the Gen 7 chat on branch box/coordination at 03:14 UTC. The phase 1 collector is drained the
# graceful way and can be resumed: rm ~/work/runs/gen7-phase1-$BOX/STOP && sudo systemctl start arena-gen7
set -uo pipefail
BOX=$BOXCTL_BOX; W=$HOME/work; G=$W/g8; RUN=$W/runs/gen7-phase1-$BOX; SHA=b6ad822d6c464359d053ddc1b876afbda46e8442
if systemctl is-active --quiet arena-gen7; then
  touch "$RUN/STOP"
  echo "$(date -u +%FT%TZ) STOP written by the Gen 8 chat (g8) on Max's authority; see branch box/coordination. Resume: rm STOP && sudo systemctl start arena-gen7" >> "$RUN.g8-note.txt"
  for i in $(seq 1 120); do systemctl is-active --quiet arena-gen7 || break; sleep 5; done
fi
echo "arena-gen7: $(systemctl is-active arena-gen7); phase 1 boards on this box: $(ls "$RUN/receipts" 2>/dev/null | wc -l); failures: $(ls "$RUN/failures" 2>/dev/null | wc -l); publisher: $(systemctl is-active arena-gen7-publish)"
systemctl is-active --quiet arena-gen7 && { echo "the collector has not drained after 10 minutes; nothing else changed, no Gen 8 job queued"; exit 1; }
git -C "$G/src" fetch -q --depth 1 origin "$SHA" && git -C "$G/src" checkout -q FETCH_HEAD || { echo "could not check out $SHA"; exit 1; }
echo "g8 source: $(git -C "$G/src" log -1 --format='%h %s' | cut -c1-90)"
# queue runner, second form: a line "@source SHA" changes the checkout between jobs
cat > "$G/queue.sh" <<'SH'
#!/usr/bin/env bash
# Runs the lines of ~/work/g8/queue.txt one after another, each job on every core.
#   NAME PAIR FIRST DEALS SEED [extra gen8_match.py flags]    a match (resumes if its folder exists)
#   @source SHA                                               check out that commit of the Gen 8 prototype before the next job
#   # ...                                                     skipped (still counted in queue.pos)
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
cd "$G/src" || exit 1
log() { echo "$(date -u +%FT%TZ) $*" >> "$G/queue.log"; }
while true; do
  pos=$(cat "$G/queue.pos"); line=$(sed -n "$((pos + 1))p" "$G/queue.txt")
  if [ -z "$line" ]; then sleep 15; continue; fi
  case "$line" in
    \#*) echo $((pos + 1)) > "$G/queue.pos"; continue ;;
    @source\ *) sha=${line#@source }
      until git fetch -q --depth 1 origin "$sha" && git checkout -q FETCH_HEAD; do log "could not check out $sha; retrying"; sleep 60; done
      log "source now $(git log -1 --format='%h %s' | cut -c1-80)"; echo $((pos + 1)) > "$G/queue.pos"; continue ;;
  esac
  set -- $line; name=$1; pair=$2; first=$3; deals=$4; seed=$5; shift 5
  log "start $name: $pair deals $first+$deals seed $seed $* (source $(git rev-parse --short HEAD))"
  "$PY" -u scripts/gen8_match.py --source "$CAP" --bots configs/gen8-proto-bots.json --pair "$pair" --first "$first" --deals "$deals" \
      --seed "$seed" --workers "$(nproc)" --out "$G/runs/$name" "$@" >> "$G/runs/$name.log" 2>&1
  log "end $name: exit $?"
  echo $((pos + 1)) > "$G/queue.pos"
done
SH
sudo systemctl restart g8-queue
case "$BOX" in
  azure1) JOB="x1-8s-v-7s 8s-32~7s-32 0 2400 81
c0-n-v4-v-v0 n-v4~n-v0 0 4000 83
c1-8s-v4-v-v0 8s-32~8s-32-v0 0 2400 83" ;;
  azure4) JOB="x1-8p-v-7s 8p-32~7s-32 0 2400 81
c1-7s-v4-v-v0 7s-32~7s-32-v0 0 2400 83" ;;
  *) echo "no Gen 8 jobs for $BOX"; exit 1 ;;
esac
echo "$JOB" >> "$G/queue.txt"
sleep 60
echo "queue: $(systemctl is-active g8-queue); $(tail -1 "$G/queue.log" 2>/dev/null | cut -c1-160)"
tail -2 "$G"/runs/x1-*.log 2>/dev/null | cut -c1-200
uptime | sed 's/.*load/load/'
