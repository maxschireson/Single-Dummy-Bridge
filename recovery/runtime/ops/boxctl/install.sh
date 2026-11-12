#!/usr/bin/env bash
# Install or update the boxctl agent on this machine (Ubuntu/Debian with systemd).
#
#   bash install.sh <commit> [box-name]
#
# <commit> is the maxschireson/Single-Dummy-Bridge commit to take agent.py from.
# [box-name] defaults to the hostname; lowercase letters, digits and hyphens.
# Run it as the login user the agent should run as (not root); it needs sudo
# only to install packages and the systemd unit. Re-running it updates the agent
# and keeps the existing key, configuration and command history.
set -euo pipefail

REF="${1:-}"
BOX="${2:-$(hostname -s | tr '[:upper:]_' '[:lower:]-')}"
OWNER_REPO="${BOXCTL_OWNER_REPO:-maxschireson/Single-Dummy-Bridge}"
REPO_URL="${BOXCTL_REPO_URL:-git@github.com:${OWNER_REPO}.git}"
RAW="https://raw.githubusercontent.com/${OWNER_REPO}/${REF}/ops/boxctl"
DIR="$HOME/.boxctl"
KEY="$HOME/.ssh/boxctl_github"

die() { echo "boxctl install: $*" >&2; exit 1; }

[[ "$REF" =~ ^[0-9a-f]{7,40}$ ]] || die "usage: bash install.sh <commit> [box-name]"
[ "$(id -u)" -ne 0 ] || die "run this as your normal login user, not root"
[[ "$BOX" =~ ^[a-z0-9][a-z0-9-]{0,39}$ ]] || die "box name '$BOX' must be lowercase letters, digits and hyphens; pass one as the second argument"
sudo -n true 2>/dev/null || die "this user needs passwordless sudo to install the service"
command -v systemctl >/dev/null || die "systemd is required"

missing=()
for c in git python3 ssh-keygen curl; do command -v "$c" >/dev/null || missing+=("$c"); done
if [ ${#missing[@]} -gt 0 ]; then
  command -v apt-get >/dev/null || die "missing ${missing[*]}; install them and re-run"
  pkgs=()
  for c in "${missing[@]}"; do [ "$c" = ssh-keygen ] && pkgs+=(openssh-client) || pkgs+=("$c"); done
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${pkgs[@]}"
fi

mkdir -p "$DIR" "$HOME/.ssh"
chmod 700 "$DIR" "$HOME/.ssh"
curl -fsSL "$RAW/agent.py" -o "$DIR/agent.py.new"
python3 -m py_compile "$DIR/agent.py.new"
mv "$DIR/agent.py.new" "$DIR/agent.py"

[ -f "$KEY" ] || ssh-keygen -q -t ed25519 -N "" -C "boxctl-$BOX" -f "$KEY"

python3 - "$DIR/config.json" "$BOX" "$REPO_URL" "$KEY" <<'PY'
import json, os, sys
path, box, repo, key = sys.argv[1:5]
cfg = json.load(open(path)) if os.path.exists(path) else {}
cfg.update({"box": box, "repo": repo, "ssh_key": key})
cfg.setdefault("poll_s", 30)
cfg.setdefault("heartbeat_s", 300)
with open(path, "w") as f:
    json.dump(cfg, f, indent=1)
PY

sudo tee /etc/systemd/system/boxctl.service >/dev/null <<UNIT
[Unit]
Description=boxctl agent: runs commands queued on GitHub (box $BOX)
After=network-online.target
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=$HOME
ExecStart=$(command -v python3) $DIR/agent.py --config $DIR/config.json
Restart=always
RestartSec=15
# Restarting or stopping the agent must not kill jobs that its commands started.
KillMode=process
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable boxctl.service >/dev/null 2>&1
sudo systemctl restart boxctl.service

cat <<EOF

boxctl agent installed for box "$BOX" (agent.py from $REF).

Last step: add this deploy key to the repository with write access.
  1. Open https://github.com/${OWNER_REPO}/settings/keys/new
  2. Title: boxctl-$BOX
  3. Key:   $(cat "$KEY.pub")
  4. Tick "Allow write access", then "Add key".

The agent retries every 30 seconds. Once the key is in, a heartbeat appears on
branch box/$BOX/status. To watch the agent here: journalctl -u boxctl -f
EOF
