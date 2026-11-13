#!/usr/bin/env bash
# Pushes the loop's small outputs from a box to transfer/rollout-loop-<box>-20261113 every ten minutes:
# each run's results.jsonl, summary.json and manifest.json, the logs and runs.log. Episodes (large) stay on the box.
# Research data: not an arena cohort and not a feed. Never merge the transfer branch.
BOX=$1; W=$HOME/work/loop; D=$W/pub; BR=transfer/rollout-loop-$BOX-20261113
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
if [ ! -d "$D/.git" ]; then
  git init -q "$D"; git -C "$D" remote add origin ssh://git@github.com/maxschireson/Single-Dummy-Bridge.git
  if git -C "$D" fetch -q --depth 1 origin "$BR" 2>/dev/null; then git -C "$D" checkout -q -b "$BR" FETCH_HEAD; else git -C "$D" checkout -q --orphan "$BR"; fi
fi
while true; do
  for d in "$W"/runs/*/; do n=$(basename "$d"); [ -e "$d/results.jsonl" ] || continue; mkdir -p "$D/$n"
    cp -f "$d/summary.json" "$d/manifest.json" "$d/results.jsonl" "$D/$n/" 2>/dev/null
    [ -d "$d/episodes" ] && echo "$(ls "$d/episodes" | wc -l) episode files, $(du -sm "$d/episodes" | cut -f1) MB, on $BOX under ~/work/loop/runs/$n/episodes" > "$D/$n/EPISODES.txt"
  done
  for f in "$W"/runs/*.log "$W"/runs/*.json "$W"/runs/*.txt; do [ -e "$f" ] && [ "$(stat -c %s "$f")" -lt 20000000 ] && cp -f "$f" "$D/"; done
  cp -f "$W/runs.log" "$D/" 2>/dev/null
  cat > "$D/README.md" <<MD
# Rollout loop outputs: $BOX

**Work in progress. Research data, not an arena cohort and not a feed.** Outputs of the rollout loop's matches and
collections on $BOX, run from branch \`research/rollout-loop-20261113\` (\`runs.log\` names each job's source commit):
match folders with one row a board, summaries and logs. Full records stay on the box. Never merge this branch.
MD
  git -C "$D" add -A
  if ! git -C "$D" diff --cached --quiet; then
    git -C "$D" -c user.name="loop box publisher" -c user.email=noreply@anthropic.com commit -q \
      -m "Rollout loop outputs from $BOX, $(date -u +%FT%TZ)" \
      -m "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxDPjdoFBFtyygdYP4j"
    git -C "$D" push -q origin "$BR" 2>&1 | tail -1
  fi
  sleep 600
done
