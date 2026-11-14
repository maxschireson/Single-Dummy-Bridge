#!/usr/bin/env bash
# Install or update mailbridge on a box. Usage: install.sh <commit> <box-name>
# Needs the boxctl deploy key (~/.ssh/boxctl_github) and branch mail/coord on GitHub.
set -euo pipefail
REF="$1"; BOX="$2"
RAW="https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/${REF}/ops/mailbridge"
DIR="$HOME/mailbridge"; CFG="$HOME/.mailbridge"
mkdir -p "$DIR" "$CFG"; chmod 700 "$CFG"
curl -fsSL "$RAW/mailbridge.py" -o "$DIR/mailbridge.py.new"
python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$DIR/mailbridge.py.new"
mv "$DIR/mailbridge.py.new" "$DIR/mailbridge.py"
REPO_URL=$(python3 -c "import json,os; print(json.load(open(os.path.expanduser('~/.boxctl/config.json')))['repo'])" 2>/dev/null \
  || echo "git@github.com:maxschireson/Single-Dummy-Bridge.git")
[ -f "$CFG/allow" ] || printf 'randal@cs.jhu.edu\nmschireson@gmail.com\n' > "$CFG/allow"
sudo tee /etc/systemd/system/mailbridge.service >/dev/null <<EOF
[Unit]
Description=mailbridge: mailbox relay for a Claude session (ops/mailbridge)
After=network-online.target
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=$DIR
ExecStart=$(command -v python3) $DIR/mailbridge.py --box $BOX --repo-url $REPO_URL --ssh-key $HOME/.ssh/boxctl_github
Restart=always
RestartSec=30
Nice=10
CPUQuota=20%
MemoryMax=400M

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable mailbridge >/dev/null 2>&1
sudo systemctl restart mailbridge
sleep 20
systemctl is-active mailbridge
journalctl -u mailbridge -n 20 --no-pager | sed -E 's/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+/<addr>/g'
