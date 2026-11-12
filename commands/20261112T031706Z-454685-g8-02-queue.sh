# boxctl: timeout=300
# boxctl: timeout=300
# Gen 8 prototype (g8 chat): a job queue and a results publisher under ~/work/g8. Starts nothing heavy by itself:
# the queue is empty until jobs are appended to ~/work/g8/queue.txt.
set -uo pipefail
W=$HOME/work; G=$W/g8; BOX=$BOXCTL_BOX
mkdir -p "$G/runs"; touch "$G/queue.txt"; [ -e "$G/queue.pos" ] || echo 0 > "$G/queue.pos"
cat > "$G/queue.sh" <<'SH'
#!/usr/bin/env bash
# Runs the jobs listed in ~/work/g8/queue.txt one after another, each on every core.
# A line: NAME PAIR FIRST DEALS SEED [extra gen8_match.py flags]. Lines starting with # are skipped but counted.
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
cd "$G/src" || exit 1
while true; do
  pos=$(cat "$G/queue.pos"); line=$(sed -n "$((pos + 1))p" "$G/queue.txt")
  if [ -z "$line" ]; then sleep 15; continue; fi
  case "$line" in \#*) echo $((pos + 1)) > "$G/queue.pos"; continue ;; esac
  set -- $line; name=$1; pair=$2; first=$3; deals=$4; seed=$5; shift 5
  echo "$(date -u +%FT%TZ) start $name: $pair deals $first+$deals seed $seed $* (source $(git rev-parse --short HEAD))" >> "$G/queue.log"
  "$PY" -u scripts/gen8_match.py --source "$CAP" --bots configs/gen8-proto-bots.json --pair "$pair" --first "$first" --deals "$deals" \
      --seed "$seed" --workers "$(nproc)" --out "$G/runs/$name" "$@" >> "$G/runs/$name.log" 2>&1
  echo "$(date -u +%FT%TZ) end $name: exit $?" >> "$G/queue.log"
  echo $((pos + 1)) > "$G/queue.pos"
done
SH
cat > "$G/pub.sh" <<'SH'
#!/usr/bin/env bash
# Pushes run summaries and per-board results (not full records) to transfer/gen8-proto-<box>-20261112 every five minutes.
BOX=$1; G=$HOME/work/g8; P=$G/pub; BR=transfer/gen8-proto-$BOX-20261112
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
if [ ! -d "$P/.git" ]; then
  git init -q "$P"; git -C "$P" remote add origin ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git
  if git -C "$P" fetch -q --depth 1 origin "$BR" 2>/dev/null; then git -C "$P" checkout -q -b "$BR" FETCH_HEAD; else git -C "$P" checkout -q --orphan "$BR"; fi
fi
while true; do
  for d in "$G"/runs/*/; do
    n=$(basename "$d"); [ -e "$d/results.jsonl" ] || continue
    mkdir -p "$P/$n"; cp -f "$d/summary.json" "$d/manifest.json" "$d/results.jsonl" "$P/$n/" 2>/dev/null
  done
  cp -f "$G"/runs/*.log "$G/queue.txt" "$G/queue.pos" "$G/queue.log" "$P/" 2>/dev/null
  cat > "$P/README.md" <<MD
# Gen 8 prototype test results: $BOX

**Work in progress. Test data, not an arena cohort and not a feed.** Fork-free duplicate matches
played by \`scripts/gen8_match.py\` on branch \`feature/gen8-prototype-20261112\`, on fresh random
deals. One folder per match: \`summary.json\`, \`results.jsonl\` (one line per board) and
\`manifest.json\` (the bots' full settings). \`queue.txt\` is the job list. Never merge this branch.
MD
  git -C "$P" add -A
  if ! git -C "$P" diff --cached --quiet; then
    git -C "$P" -c user.name="g8 box publisher" -c user.email=noreply@anthropic.com commit -q \
      -m "Gen 8 prototype test results from $BOX, $(date -u +%FT%TZ)" \
      -m "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxEA6NwcnXPZb3BY1s9"
    git -C "$P" push -q origin "$BR" 2>&1 | tail -1
  fi
  sleep 300
done
SH
chmod +x "$G/queue.sh" "$G/pub.sh"
CAPS="--setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1"
for u in g8-queue g8-publish; do sudo systemctl stop $u 2>/dev/null; sudo systemctl reset-failed $u 2>/dev/null; done
sudo systemd-run --quiet --unit=g8-queue --uid="$(id -un)" --setenv=HOME="$HOME" $CAPS --property=Restart=on-failure --property=RestartSec=20 \
  --working-directory="$G" -- "$G/queue.sh"
sudo systemd-run --quiet --unit=g8-publish --uid="$(id -un)" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 \
  --working-directory="$G" -- "$G/pub.sh" "$BOX"
sleep 3
echo "queue: $(systemctl is-active g8-queue); publisher: $(systemctl is-active g8-publish); jobs listed: $(wc -l < "$G/queue.txt"); position $(cat "$G/queue.pos")"
