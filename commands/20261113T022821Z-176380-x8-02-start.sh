# boxctl: timeout=600
# boxctl: timeout=600
# x8 session, azure6 (Max, 02:20 and 02:27 UTC 13 Nov): start the two 8X matches as one unit (x1, then x2 on the same deals)
# and a publisher unit that pushes results to transfer/x8-azure6-20261113 every 10 minutes. Everything under ~/work/x8.
set -euo pipefail
W=$HOME/work/x8; S=$W/src; PY=$HOME/work/venv/bin/python
mkdir -p "$W/runs"
cat > "$W/queue.sh" <<'Q'
#!/bin/bash
set -uo pipefail
W=$HOME/work/x8; S=$W/src; PY=$HOME/work/venv/bin/python
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE=
cd "$S"
for job in "x1 8xr0-ft1~8p-32-v41" "x2 8xr0-v41~8p-32-v41"; do
  set -- $job
  echo "$(date -u +%FT%TZ) start $1 ($2) source $(git rev-parse --short HEAD)" >> "$W/queue.log"
  "$PY" scripts/x8_match.py --feature-forks --source $HOME/work/capsule-gen7-capture/recovery --bots configs/x8-bots.json \
    --pair "$2" --deals 1600 --seed 131 --workers 8 --out "$W/runs/$1" >> "$W/runs/$1.log" 2>&1
  echo "$(date -u +%FT%TZ) end $1: exit $?" >> "$W/queue.log"
done
Q
cat > "$W/publish.sh" <<'P'
#!/bin/bash
# copy logs, match folders (results.jsonl, summary.json, manifest.json) and pooled forks to the transfer branch, every 10 minutes
set -uo pipefail
W=$HOME/work/x8; S=$W/src; PY=$HOME/work/venv/bin/python; B=transfer/x8-azure6-20261113; P=$W/publish
read -r REPO KEY < <("$PY" -c "import json,os; c=json.load(open(os.path.expanduser('~/.boxctl/config.json'))); print(c['repo'], os.path.expanduser(c.get('ssh_key','')))")
export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes"
while true; do
  rm -rf "$P"; mkdir -p "$P"; cd "$P"; git init -q; git checkout -q -b "$B"
  cat > README.md <<R
# 8X matches on azure6 (x8 session)

**Research data, not an arena cohort and not a feed; never merge.** Matches of the 8X bot (engine gen8x, branch
feature/gen8x-rollout-bot-20261113; each match's manifest.json names its source commit), run by scripts/x8_match.py
--feature-forks. results.jsonl: one row a board; search.x8_forks: the feature forks; forks-*.txt: scripts/x8_forks.py.
x1: 8xr0-ft1 (rollout net v1 ft) against 8p-32-v41. x2: 8xr0-v41 (rollout net v4.1) against 8p-32-v41, same deals (seed 131).
R
  cp "$W/queue.log" . 2>/dev/null || true
  for r in "$W"/runs/x*; do
    [ -d "$r" ] || continue; n=$(basename "$r"); mkdir -p "$n"
    cp "$r"/results.jsonl "$r"/summary.json "$r"/manifest.json "$n"/ 2>/dev/null || true
    cp "$W/runs/$n.log" . 2>/dev/null || true
    (cd "$S" && "$PY" scripts/x8_forks.py "$r") > "forks-$n.txt" 2>&1 || true
  done
  git add -A; git -c user.name=x8-azure6 -c user.email=noreply@anthropic.com commit -q -m "x8 azure6 results $(date -u +%FT%TZ)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxCQ6vgu8n15HtXEr6u"
  git push -q -f "$REPO" "HEAD:refs/heads/$B" 2>&1 | grep -v "^remote:" | tail -2
  cd "$W"; sleep 600
done
P
chmod +x "$W/queue.sh" "$W/publish.sh"
sudo systemctl stop x8-queue x8-publish 2>/dev/null || true
sudo systemctl reset-failed x8-queue x8-publish 2>/dev/null || true
sudo systemd-run --unit=x8-queue --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- "$W/queue.sh"
sudo systemd-run --unit=x8-publish --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" --property=Restart=on-failure -- "$W/publish.sh"
sleep 90
systemctl is-active x8-queue x8-publish; cat "$W/queue.log"; tail -2 "$W/runs/x1.log"; uptime
journalctl -u x8-publish -n 5 --no-pager | cut -c1-200
