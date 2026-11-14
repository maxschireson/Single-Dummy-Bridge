# boxctl: timeout=90
set -euo pipefail
printf 'Services\n'
systemctl list-units --all --no-pager --plain | grep -E 'ben|rollout|loop-collect' || true
printf 'BEN directories\n'
find "$HOME" -maxdepth 4 -type d -iname '*ben*' 2>/dev/null | head -40
printf 'Listeners\n'
ss -ltnp | head -35
printf 'Current launcher\n'
cat "$HOME/work/rollout-experiments-20261114/run.sh"
printf 'Clock\n'
date -u +%FT%TZ
