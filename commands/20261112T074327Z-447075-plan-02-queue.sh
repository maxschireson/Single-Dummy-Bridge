# boxctl: timeout=300
# boxctl: timeout=300
# plan session: a job queue and a results publisher under ~/work/plan. Starts nothing heavy by itself:
# the queue is empty until lines are appended to ~/work/plan/queue.txt.
set -uo pipefail
W=$HOME/work; P=$W/plan; BOX=$BOXCTL_BOX
mkdir -p "$P/runs"; touch "$P/queue.txt"; [ -e "$P/queue.pos" ] || echo 0 > "$P/queue.pos"
cat > "$P/queue.sh" <<'SH'
#!/usr/bin/env bash
# Runs the lines of ~/work/plan/queue.txt one after another.
#   NAME COMMAND...        run COMMAND with bash in ~/work/plan/src; output to runs/NAME.log. In COMMAND, $PY is the
#                          venv's python, $P is ~/work/plan, $NETS the policy nets, $R is runs/NAME (a file prefix)
#   @source SHA            check out that commit before the next job
#   # ...                  skipped (still counted in queue.pos)
export P=$HOME/work/plan; export PY=$HOME/work/venv/bin/python
cd "$P/src" || exit 1
log() { echo "$(date -u +%FT%TZ) $*" >> "$P/queue.log"; }
while true; do
  pos=$(cat "$P/queue.pos"); line=$(sed -n "$((pos + 1))p" "$P/queue.txt")
  if [ -z "$line" ]; then sleep 15; continue; fi
  case "$line" in
    \#*) echo $((pos + 1)) > "$P/queue.pos"; continue ;;
    @source\ *) sha=${line#@source }
      until git fetch -q --depth 1 origin "$sha" && git checkout -q FETCH_HEAD; do log "could not check out $sha; retrying"; sleep 60; done
      log "source now $(git log -1 --format='%h %s' | cut -c1-80)"; echo $((pos + 1)) > "$P/queue.pos"; continue ;;
  esac
  name=${line%% *}; cmd=${line#* }
  export NETS=$(cat "$P/nets.txt"); export R=$P/runs/$name
  log "start $name (source $(git rev-parse --short HEAD)): $cmd"
  bash -c "$cmd" >> "$P/runs/$name.log" 2>&1
  log "end $name: exit $?"
  echo $((pos + 1)) > "$P/queue.pos"
done
SH
cat > "$P/pub.sh" <<'SH'
#!/usr/bin/env bash
# Pushes run outputs (json rows gzipped, logs, the queue) to transfer/plan-leverage-<box>-20261112 every five minutes.
BOX=$1; P=$HOME/work/plan; D=$P/pub; BR=transfer/plan-leverage-$BOX-20261112
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
if [ ! -d "$D/.git" ]; then
  git init -q "$D"; git -C "$D" remote add origin ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git
  if git -C "$D" fetch -q --depth 1 origin "$BR" 2>/dev/null; then git -C "$D" checkout -q -b "$BR" FETCH_HEAD; else git -C "$D" checkout -q --orphan "$BR"; fi
fi
while true; do
  for f in "$P"/runs/*.json; do [ -e "$f" ] || continue; n=$(basename "$f"); [ "$D/$n.gz" -nt "$f" ] || gzip -c "$f" > "$D/$n.gz"; done
  for d in "$P"/runs/*/; do n=$(basename "$d"); [ -e "$d/results.jsonl" ] || continue; mkdir -p "$D/$n"; cp -f "$d/summary.json" "$d/manifest.json" "$d/results.jsonl" "$D/$n/" 2>/dev/null; done
  cp -f "$P"/runs/*.log "$P/queue.txt" "$P/queue.pos" "$P/queue.log" "$D/" 2>/dev/null
  cat > "$D/README.md" <<MD
# Plan-leverage research outputs: $BOX

**Work in progress. Research data, not an arena cohort and not a feed.** Outputs of the jobs in \`queue.txt\`, run from
branch \`research/plan-leverage-20261112\` (each job's log names its source commit): bench rows as \`*.json.gz\`
(read them with \`scripts/plan_report.py\` after gunzip), logs, and match folders. Never merge this branch.
MD
  git -C "$D" add -A
  if ! git -C "$D" diff --cached --quiet; then
    git -C "$D" -c user.name="plan box publisher" -c user.email=noreply@anthropic.com commit -q \
      -m "Plan-leverage research outputs from $BOX, $(date -u +%FT%TZ)" \
      -m "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxETgngTN3WCMv4MhwW"
    git -C "$D" push -q origin "$BR" 2>&1 | tail -1
  fi
  sleep 300
done
SH
chmod +x "$P/queue.sh" "$P/pub.sh"
CAPS="--setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1 --setenv=BRIDGE_DDS_CACHE="
for u in plan-queue plan-publish; do sudo systemctl stop $u 2>/dev/null; sudo systemctl reset-failed $u 2>/dev/null; done
sudo systemd-run --quiet --unit=plan-queue --uid="$(id -un)" --setenv=HOME="$HOME" $CAPS --property=Restart=on-failure --property=RestartSec=20 \
  --working-directory="$P" -- "$P/queue.sh"
sudo systemd-run --quiet --unit=plan-publish --uid="$(id -un)" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 \
  --working-directory="$P" -- "$P/pub.sh" "$BOX"
sleep 3
echo "queue: $(systemctl is-active plan-queue); publisher: $(systemctl is-active plan-publish); jobs listed: $(wc -l < "$P/queue.txt"); position $(cat "$P/queue.pos")"
