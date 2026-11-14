# boxctl: timeout=60
set -eu
python3 - <<'PY'
from pathlib import Path
p=Path.home()/'work/rollout-experiments-20261114/drain.py'
s=p.read_text().replace("'pid,args'", "'pid=,args='")
p.write_text(s)
PY
sudo systemctl reset-failed stu-rollout-drain
sudo systemd-run --unit=stu-rollout-drain-retry --uid="$USER" --property=RuntimeMaxSec=1250 "$HOME/work/loop/venv/bin/python" "$HOME/work/rollout-experiments-20261114/drain.py"
