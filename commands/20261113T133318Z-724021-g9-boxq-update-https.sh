# boxctl: timeout=120
# boxctl: timeout=300
# Update the Gen 9 queue's tools on this box to the tip of team/gen9 and restart g9-boxq. Running jobs (g9-job-*) are
# separate units and keep running; the server picks them up again from ~/work/g9/boxq/status.json.
set -uo pipefail
W=$HOME/work/g9; say() { echo "$(date -u +%T) $*"; }
eval "$(python3 - <<'PY'
import json, os, shlex
c = json.load(open(os.path.expanduser('~/.boxctl/config.json')))
print('export GIT_SSH_COMMAND=' + shlex.quote(f"ssh -i {os.path.expanduser(c['ssh_key'])} -o IdentitiesOnly=yes -o BatchMode=yes"))
PY
)"
say "before: $(git -C "$W/channel" log -1 --format='%h %s' | cut -c1-70)"
git -C "$W/channel" fetch -q --depth 1 origin team/gen9 && git -C "$W/channel" reset -q --hard FETCH_HEAD || { say "fetch failed"; exit 1; }
say "after:  $(git -C "$W/channel" log -1 --format='%h %s' | cut -c1-70)"
say "jobs running: $(systemctl list-units --type=service --state=active --no-legend 'g9-job-*' | awk '{print $1}' | tr '\n' ' ')"
sudo systemctl restart g9-boxq && sleep 20
say "g9-boxq: $(systemctl is-active g9-boxq); jobs running: $(systemctl list-units --type=service --state=active --no-legend 'g9-job-*' | awk '{print $1}' | tr '\n' ' ')"
journalctl -u g9-boxq -n 6 --no-pager | cut -c1-200
