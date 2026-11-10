"""Resume the existing experiment from a persistent desktop terminal.

The command-tool session ended with the chat turn. This launcher runs in the
desktop session instead, waits for any existing writer, and never duplicates it.
The frozen training implementation and checkpoints are unchanged.
"""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

repo = Path(__file__).resolve().parents[1]
config = repo/'configs/bidding_structure.json'
cfg = json.loads(config.read_text())
root = Path(cfg['out'])
launcher_lock = (root/'desktop-launcher.lock').open('a+')
fcntl.flock(launcher_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
os.chdir(repo)


def status(phase, **extra):
    value = dict(phase=phase, pid=os.getpid(), utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **extra)
    path = root/'desktop-launcher-state.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n')
    temp.replace(path)
    print(json.dumps(value), flush=True)


writer_lock = (root/'supervisor.lock').open('a+')
status('waiting_for_existing_writer')
while True:
    if (root/'complete.json').exists():
        status('already_complete')
        sys.exit(0)
    try:
        fcntl.flock(writer_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(writer_lock, fcntl.LOCK_UN)
        break
    except BlockingIOError:
        time.sleep(2)

env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
           TF_CPP_MIN_LOG_LEVEL='3', TF_ENABLE_ONEDNN_OPTS='0')
status('running')
with (root/'desktop-launcher.log').open('a') as log:
    process = subprocess.run([sys.executable, str(repo/'scripts/run_bidding_structure.py'),
                              '--config', str(config), '--stage', 'run'],
                             env=env, stdout=log, stderr=subprocess.STDOUT)
status('complete' if process.returncode == 0 and (root/'complete.json').exists() else 'failed',
       returncode=process.returncode)
sys.exit(process.returncode)
