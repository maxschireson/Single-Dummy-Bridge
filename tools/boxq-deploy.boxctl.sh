# boxctl: timeout=1800
# Start the Gen 9 box queue (tools/boxq.py) on this box, for g9, once the allocation table on box/coordination gives
# the box to g9. Queue it with:  python3 ops/boxctl/client.py send azure4 --file tools/boxq-deploy.boxctl.sh --slug g9-boxq
# Set TAKEOVER=1 in the first line below only after 13:10 UTC with no "azure4 released" line from g8 on the board:
# g8's entry of 07:27 asks g9 to stop g8-queue, g8-tune and g8-publish then; their matches resume from results.jsonl.
TAKEOVER=0
set -uo pipefail
BOX=${BOXCTL_BOX:?}; W=$HOME/work/g9; mkdir -p "$W"
say() { echo "$(date -u +%T) $*"; }

g8_units="g8-queue g8-tune g8-publish"
active=""; for u in $g8_units; do systemctl is-active --quiet "$u" && active="$active $u"; done
if [ -n "$active" ]; then
  if [ "$TAKEOVER" != 1 ]; then say "g8 units still active:$active. Nothing changed; wait for g8's 'released' line or set TAKEOVER=1 after 13:10."; exit 3; fi
  say "stopping$active (g8's instruction of 07:27 UTC; their matches resume from results.jsonl)"
  sudo systemctl stop $active
fi

# reach GitHub as the boxctl agent does
eval "$(python3 - <<'PY'
import json, os, shlex
c = json.load(open(os.path.expanduser('~/.boxctl/config.json')))
print('export WORKQ_REPO=' + shlex.quote(c['repo_url']))
print('export GIT_SSH_COMMAND=' + shlex.quote(f"ssh -i {os.path.expanduser(c['ssh_key'])} -o IdentitiesOnly=yes -o BatchMode=yes"))
PY
)"
export WORKQ_TRAILERS="Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxCeTswS4ptZevoA7dH"

say "== channel tools"
if [ -d "$W/channel/.git" ]; then git -C "$W/channel" fetch -q --depth 1 origin team/gen9 && git -C "$W/channel" reset -q --hard FETCH_HEAD
else git clone -q --depth 1 --single-branch -b team/gen9 "$WORKQ_REPO" "$W/channel"; fi
say "tools at $(git -C "$W/channel" log -1 --format='%h %s' | cut -c1-70)"

say "== unattended upgrades list restarts instead of making them (p41, board 06:31); this box only"
echo "\$nrconf{restart} = 'l';" | sudo tee /etc/needrestart/conf.d/50-list-only.conf >/dev/null && say "needrestart: list only"

say "== what jobs will find (report only)"
PY=$HOME/work/venv/bin/python; [ -x "$PY" ] || PY=$(command -v python3)
say "{python} is $PY ($("$PY" -V 2>&1))"
for m in numpy h5py tensorflow keras; do
  "$PY" -c "import $m; print('$m', getattr($m, '__version__', '?'))" 2>/dev/null || say "missing in {python}: $m"
done
CAP=$HOME/work/capsule-gen7-capture/recovery
[ -f "$CAP/manifest.json" ] && say "capsule: $CAP ($(python3 -c "import json; print(len(json.load(open('$CAP/manifest.json'))['bots']), 'bots')" 2>/dev/null))" || say "capsule MISSING at $CAP"
say "disk free in ~/work: $(df -h "$HOME/work" | awk 'NR==2{print $4}'); CPUs $(nproc)"

say "== the queue"
sudo systemctl stop g9-boxq 2>/dev/null; sudo systemctl reset-failed g9-boxq 2>/dev/null || true
python3 "$W/channel/tools/boxq.py" install --box "$BOX" --cores "$(nproc)" || { say "FAILED to start g9-boxq"; exit 1; }
sleep 45
say "g9-boxq: $(systemctl is-active g9-boxq)"
journalctl -u g9-boxq -n 15 --no-pager 2>/dev/null | cut -c1-200
[ -f "$W/boxq/status.json" ] && python3 -c "import json; s=json.load(open('$W/boxq/status.json')); print({k: v['state'] for k, v in s['jobs'].items()}, s.get('bad_jobs'))"
say "load $(cut -d' ' -f1-3 /proc/loadavg); memory free $(free -g | awk '/Mem/{print $7}') GB"
