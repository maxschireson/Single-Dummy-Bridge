# boxctl: timeout=60
set -euo pipefail
W="$HOME/work/rollout-experiments-20261114"
if grep -q '"status": "drained"' "$W/drain-status.json"; then cat "$W/drain-status.json"; exit 0; fi
sudo systemctl stop stu-rollout-drain-retry
python3 - <<'PY'
from pathlib import Path
p=Path.home()/'work/rollout-experiments-20261114/drain.py'
s=p.read_text().replace('import json, os, pathlib, signal, subprocess, time','import json, os, pathlib, signal, subprocess, time, select')
old="""    if children(pid):
        time.sleep(.005); continue
    os.kill(pid,signal.SIGSTOP)
    if children(pid):
        os.kill(pid,signal.SIGCONT); time.sleep(.005); continue
"""
new="""    old = children(pid)
    fds = []
    try:
        for worker in old:
            try: fds.append(os.pidfd_open(worker))
            except ProcessLookupError: pass
        if fds:
            ready, _, _ = select.select(fds, [], [], 30)
            if not ready: continue
        os.kill(pid,signal.SIGSTOP)
        # Pool shutdown starts only after result collection; let its remaining
        # workers exit while preventing the parent from submitting a new batch.
        deadline = time.monotonic()+5
        while children(pid) and time.monotonic()<deadline:
            if fds and len(select.select(fds, [], [], .01)[0]) == len(fds):
                break  # exited children may remain zombies until their parent reaps
            time.sleep(.001)
        remaining = children(pid)
        live = []
        for worker in remaining:
            try:
                state=pathlib.Path(f'/proc/{worker}/stat').read_text().split(') ',1)[1].split()[0]
                if state != 'Z': live.append(worker)
            except FileNotFoundError: pass
        if live:
            os.kill(pid,signal.SIGCONT)
            time.sleep(.01)
            continue
    finally:
        for fd in fds: os.close(fd)
"""
assert old in s
p.write_text(s.replace(old,new))
PY
sudo systemd-run --unit=stu-rollout-drain-event --uid="$USER" --property=RuntimeMaxSec=1250 "$HOME/work/loop/venv/bin/python" "$W/drain.py"
