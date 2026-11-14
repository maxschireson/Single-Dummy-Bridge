# boxctl: timeout=90
set -euo pipefail
for d in "$HOME/work/benconf" "$HOME/work/loop/ben"; do
  find "$d" -maxdepth 2 -type f -printf '%p %s\n' 2>/dev/null | head -35
done
systemctl cat ben-server@.service 2>/dev/null || true
git -C "$HOME/work/ben" rev-parse HEAD
"$HOME/work/ben-venv/bin/python" -c 'import tensorflow as tf; print(tf.__version__)'
find "$HOME/work/ben/models" -maxdepth 2 -type f -printf '%f %s\n' 2>/dev/null | head -25
