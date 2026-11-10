"""Supervise existing locked runners and persist exit/signal evidence.

Does not change data, model or optimizer settings. Missing final exit evidence
indicates an unobserved supervisor termination, not a diagnosed training failure.
"""
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
lock = (ROOT / 'supervisor.lock').open('a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
events = (ROOT / 'supervisor-events.jsonl').open('a', buffering=1)
children = {}

def record(event, **kw):
    events.write(json.dumps(dict(event=event, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        supervisor_pid=os.getpid(), **kw)) + '\n')
    events.flush()
    os.fsync(events.fileno())

def stop(signum, frame):
    record('signal', signal=signum)
    for p in children.values():
        if p.poll() is None:
            os.killpg(p.pid, signum)
    raise SystemExit(128 + signum)

for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
    signal.signal(sig, stop)
record('started', python=sys.executable)
jobs = {
    'belief-full1513': ['bash', str(ROOT / 'run-belief-full1513.sh')],
    'policy-full1513': [sys.executable, '-u', str(ROOT / 'scripts/run_gen6_policy_full.py'),
        '--plan', str(ROOT / 'policy-launch-plan.json')],
}
for name, cmd in jobs.items():
    if (ROOT / name / 'fit/result.json').exists():
        record('already_complete', job=name)
        continue
    with (ROOT / (name + '.log')).open('a') as log:
        children[name] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    record('launched', job=name, child_pid=children[name].pid, command=cmd)
reported = set()
while len(reported) < len(children):
    state = {}
    for name, p in children.items():
        code = p.poll()
        state[name] = dict(pid=p.pid, exit_code=code)
        if code is not None and name not in reported:
            record('exited', job=name, exit_code=code)
            reported.add(name)
    target = ROOT / 'supervisor-status.json'
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(dict(updated=time.time(), jobs=state), indent=2) + '\n')
    temp.replace(target)
    if len(reported) < len(children):
        time.sleep(5)
record('finished')
