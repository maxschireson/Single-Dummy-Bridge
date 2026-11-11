"""Publish the component arena to its own GitHub feed branch."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from export_component_mix import export

def git(root,*args):
    return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True)

def publish(run,publication,diagnostic=None):
    export(run,publication)
    backup=publication/'recovery';backup.mkdir(exist_ok=True)
    for name in ('manifest.json','state.json','heartbeat.json','schedule.json','corpus.jsonl'):
        shutil.copy2(run/name,backup/name)
    if diagnostic:
        target=backup/'initial-diagnostic';target.mkdir(exist_ok=True)
        for name in ('manifest.json','state.json','corpus.jsonl'):
            shutil.copy2(diagnostic/name,target/name)
    # Preserve complete episodes, including audited forks, for cross-chat recovery.
    for source,target in [(run,backup),(diagnostic,backup/'initial-diagnostic')]:
        if source is None:continue
        episodes=target/'episodes';episodes.mkdir(exist_ok=True)
        for path in (source/'episodes').glob('*.json.gz'):
            dest=episodes/path.name
            if not dest.exists():shutil.copy2(path,dest)
    git(publication,'add','arena','recovery')
    if git(publication,'status','--porcelain').stdout.strip():
        count=json.loads((run/'state.json').read_text())['completed']
        git(publication,'commit','-m',f'Publish Gen4 hybrid mix: {count} completed hands')
    git(publication,'push','-u','origin','arena-recovery-feed')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path)
    p.add_argument('--publication',required=True,type=Path);p.add_argument('--diagnostic',type=Path)
    p.add_argument('--once',action='store_true');a=p.parse_args()
    while True:
        try:
            publish(a.run,a.publication,a.diagnostic)
            (a.run/'publisher-status.json').write_text(json.dumps(dict(epoch=time.time(),status='published')))
            if a.once or json.loads((a.run/'state.json').read_text())['completed']>=json.loads((a.run/'manifest.json').read_text())['target']:return
        except Exception as e:
            (a.run/'publisher-status.json').write_text(json.dumps(dict(epoch=time.time(),status='retrying',error=str(e))))
            if a.once:raise
        time.sleep(60)

if __name__=='__main__':main()
