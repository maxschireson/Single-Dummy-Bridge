# boxctl: timeout=300
# boxctl: timeout=300
# g8: this box got the first form of the queue runner, which does not know "@source" lines, so the multi-system match
# and two others started on the old checkout and failed at once. Install the current runner (as on azure1 and azure4:
# "@source SHA" between jobs, every processor, solver cache off) and queue those matches again.
set -uo pipefail
G=$HOME/work/g8
cat > "$G/queue.sh" <<'SH'
#!/usr/bin/env bash
# Runs the lines of ~/work/g8/queue.txt one after another, each job on every core.
#   NAME PAIR FIRST DEALS SEED [extra gen8_match.py flags]    a match (resumes if its folder exists)
#   @source SHA                                               check out that commit of the Gen 8 prototype before the next job
#   # ...                                                     skipped (still counted in queue.pos)
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
export BRIDGE_DDS_CACHE=
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
      --seed "$seed" --workers "$(nproc --all)" --out "$G/runs/$name" "$@" >> "$G/runs/$name.log" 2>&1
  log "end $name: exit $?"
  echo $((pos + 1)) > "$G/queue.pos"
done
SH
echo "before: position $(cat "$G/queue.pos") of $(wc -l < "$G/queue.txt") lines"; tail -4 "$G/queue.log" | cut -c1-150
cat >> "$G/queue.txt" <<'Q'
@source c03498c77184eb987d294c635b52b27bcfae028d
e4-8y-v-8p 8y-32~8p-32 0 2880 91 --book configs/gen8-books/mix91-2880.json.gz
g2-8x-v-trandom 8x-32~t-random 0 600 72
n1-8n-v-8p 8n-32~8p-32 0 2000 84
Q
sudo systemctl restart g8-queue
sleep 90
cat -n "$G/queue.txt" | tail -9 | cut -c1-120; echo "position $(cat "$G/queue.pos")"; tail -4 "$G/queue.log" | cut -c1-170
ls "$G/runs" | tr '\n' ' '; echo; uptime | sed 's/.*load/load/'
