"""Watch GitHub and stage logging/forking changes in detached source checkouts.

This observer never merges into or restarts a live collector. Candidates retain
their exact commits and changed-file metadata for validation before deployment.
"""
import argparse
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.selfplay import atomic_json
from ops.watch_gen6_ben_gate import REPOSITORY,git,heads,request,publish_control

TOPIC=re.compile(r'logging|fork|(?:^|[/_-])(?:v7|gen7)(?:$|[/_-])',re.I)
TRACKED_FILES={'bridge_harness/fork_audit.py','bridge_harness/gen5_arena.py','bridge_harness/runner.py',
               'bridge_harness/training.py','ops/gen5_runtime.py','ops/export_gen5.py','ops/publish_gen5.py'}


def relevant(branch,commit):
    files={f['filename'] for f in commit.get('files',[])}
    message=commit.get('commit',{}).get('message','')
    return bool(TOPIC.search(branch) or TOPIC.search(message) or files&TRACKED_FILES)


def main(a):
    a.state.mkdir(parents=True,exist_ok=True)
    with (a.state/'.observer.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic_json(a.state/'process.json',dict(pid=os.getpid(),epoch=time.time(),source=str(ROOT)))
        atomic_json(a.state/'request.json',dict(authorized_by='Max: stay tuned to GitHub for the logging/forking change preparing v7',
            source=str(ROOT),source_commit=git(ROOT,'rev-parse','HEAD'),interval_seconds=a.interval,
            since_utc=a.since,
            action='Stage relevant source commits separately; validate before any live runtime transition'))
        previous=json.loads((a.state/'watched-refs.json').read_text()) if (a.state/'watched-refs.json').exists() else {}
        updates=json.loads((a.state/'updates.json').read_text()) if (a.state/'updates.json').exists() else []
        known={r['commit'] for r in updates}
        while not (a.state/'CONTROL_STOP').exists():
            try:
                current={k:v for k,v in heads().items() if not k.startswith(('arena-','archive/')) and k!='codex/gen6-ben-followups-20261111'}
                for branch,commit in current.items():
                    if previous.get(branch)==commit or commit in known:continue
                    if not previous and not TOPIC.search(branch) and branch not in ('main','transfer/gen6-launch-package-20261111'):continue
                    detail=json.loads(request(f'https://api.github.com/repos/{REPOSITORY}/commits/{commit}'))
                    committed=detail.get('commit',{}).get('committer',{}).get('date')
                    if not previous and committed and datetime.fromisoformat(committed.replace('Z','+00:00'))<datetime.fromisoformat(a.since.replace('Z','+00:00')):continue
                    if not relevant(branch,detail):continue
                    if not re.fullmatch('[a-f0-9]{40}',commit):raise ValueError('Invalid source commit')
                    target=a.state/'staged'/commit[:12];target.parent.mkdir(exist_ok=True)
                    if not target.exists():
                        git(ROOT,'fetch','origin',commit);git(ROOT,'worktree','add','--detach',str(target),commit)
                    update=dict(branch=branch,commit=commit,previous_commit=previous.get(branch),
                        message=detail.get('commit',{}).get('message',''),
                        files=[f['filename'] for f in detail.get('files',[])],path=str(target),
                        status='staged_needs_validation',observed_epoch=time.time(),
                        url=f'https://github.com/{REPOSITORY}/commit/{commit}')
                    updates.append(update);known.add(commit);atomic_json(a.state/'updates.json',updates)
                previous=current;atomic_json(a.state/'watched-refs.json',current);atomic_json(a.state/'updates.json',updates)
                atomic_json(a.state/'status.json',dict(status='watching',checked_epoch=time.time(),staged_updates=len(updates),
                    latest=updates[-1] if updates else None,live_runtime_changed=False))
                publish_control(a.state,'arena-gen6-codex-v7-watch')
                print(json.dumps(dict(status='watching',staged_updates=len(updates),epoch=time.time())),flush=True)
                if a.once:return
            except Exception as error:
                atomic_json(a.state/'status.json',dict(status='blocked_retrying',epoch=time.time(),error=repr(error)))
                print(repr(error),flush=True)
                if a.once:raise
            time.sleep(a.interval)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,default=Path('/workspace/work/v7-logging-watch'))
    p.add_argument('--since',default='2026-11-11T04:31:00Z')
    p.add_argument('--interval',type=int,default=600);p.add_argument('--once',action='store_true');main(p.parse_args())
