"""Publish Gen5 scores/replays and complete resumable training records."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import time
from export_gen5 import export

ROOT=Path(__file__).resolve().parents[1]
def git(root,*args):return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True)
def copy_once(source,dest):
    if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)

def publish(run,out):
    export(run,out);backup=out/'recovery';backup.mkdir(exist_ok=True)
    for name in ('manifest.json','state.json','heartbeat.json','corpus.jsonl'):shutil.copy2(run/name,backup/name)
    for folder in ('episodes','receipts','artifacts','assets'):
        for path in (run/folder).rglob('*'):
            if path.is_file() and not path.name.endswith('.tmp'):copy_once(path,backup/folder/path.relative_to(run/folder))
    for path in (ROOT/'bridge_harness').glob('*.py'):copy_once(path,backup/'runtime/bridge_harness'/path.name)
    copy_once(ROOT/'bridge_harness/libbridge_dds.so',backup/'runtime/bridge_harness/libbridge_dds.so')
    for path in (ROOT/'scripts').glob('*.py'):copy_once(path,backup/'runtime/scripts'/path.name)
    for path in (ROOT/'native').glob('*.cpp'):copy_once(path,backup/'runtime/native'/path.name)
    for name in ('gen5_runtime.py','prepare_gen5.py','publish_gen5.py','export_gen5.py'):
        copy_once(ROOT/'ops'/name,backup/'runtime/ops'/name)
    for name in ('LICENSE','CREDITS.md'):copy_once(ROOT/name,backup/'runtime'/name)
    git(out,'add','arena','recovery')
    if git(out,'status','--porcelain').stdout.strip():
        n=json.loads((out/'arena/data.json').read_text())['completed'];git(out,'commit','-m',f'Gen5: {n} verified paired deals, common/native bidding')
    git(out,'push','-u','origin','arena-gen5-codex-feed')
    return json.loads((out/'arena/data.json').read_text())['completed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--publication',type=Path,required=True);p.add_argument('--once',action='store_true');a=p.parse_args()
    while True:
        try:
            n=publish(a.run,a.publication)
            (a.run/'publisher-status.json').write_text(json.dumps(dict(epoch=time.time(),status='published',completed=n)))
            if a.once or n>=json.loads((a.run/'manifest.json').read_text())['target']:break
        except Exception as e:
            (a.run/'publisher-status.json').write_text(json.dumps(dict(epoch=time.time(),status='retrying',error=str(e))))
            if a.once:raise
        time.sleep(60)
