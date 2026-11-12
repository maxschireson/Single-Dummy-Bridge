"""Publish Gen5 scores/replays and complete resumable training records."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from ops.export_gen5 import export
from bridge_harness.loop_registry import source_hash

def git(root,*args):return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True)
def copy_once(source,dest):
    if not dest.exists():dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)

def snapshot_runtime(run,backup):
    manifest=json.loads((run/'manifest.json').read_text())
    if manifest['source_sha256']!=source_hash():
        if not (backup/'runtime/bridge_harness').is_dir():
            raise ValueError('Archive runtime is missing and this checkout belongs to another cohort')
        # Finalizing an older cohort must preserve its frozen runtime verbatim.
        return False
    for path in (ROOT/'bridge_harness').glob('*.py'):copy_once(path,backup/'runtime/bridge_harness'/path.name)
    copy_once(ROOT/'bridge_harness/libbridge_dds.so',backup/'runtime/bridge_harness/libbridge_dds.so')
    for path in (ROOT/'scripts').glob('*.py'):copy_once(path,backup/'runtime/scripts'/path.name)
    for path in (ROOT/'native').glob('*.cpp'):copy_once(path,backup/'runtime/native'/path.name)
    for name in ('gen5_runtime.py','prepare_gen5.py','publish_gen5.py','export_gen5.py','watch_gen5.py'):
        source=ROOT/'ops'/name;dest=backup/'runtime/ops'/name
        if name=='watch_gen5.py' and dest.exists():shutil.copy2(source,dest)
        else:copy_once(source,dest)
    for name in ('prepare_gen5r.py','register_gen5r_report.py','prepare_gen5rz.py','prepare_gen5rz_ben.py',
                 'prepare_gen6.py','prepare_gen6_independent.py','register_gen6_report.py','smoke_gen6.py',
                 'prepare_gen7_alpha.py','smoke_gen7.py'):
        if (ROOT/'ops'/name).exists():copy_once(ROOT/'ops'/name,backup/'runtime/ops'/name)
    copy_once(ROOT/'configs/round5r.json',backup/'runtime/configs/round5r.json')
    if (ROOT/'configs/round5rz.json').exists():copy_once(ROOT/'configs/round5rz.json',backup/'runtime/configs/round5rz.json')
    if (ROOT/'configs/round5rz-ben.json').exists():copy_once(ROOT/'configs/round5rz-ben.json',backup/'runtime/configs/round5rz-ben.json')
    for name in ('round6.json','round6-cutover.json','round6-independent.json','round6-codex.json',
                 'round7-candidate-phase1.json','gen7-candidate-mix.json'):
        if (ROOT/'configs'/name).exists():copy_once(ROOT/'configs'/name,backup/'runtime/configs'/name)
    for name in ('LICENSE','CREDITS.md'):copy_once(ROOT/name,backup/'runtime'/name)
    return True

def publish(run,out):
    export(run,out);backup=out/'recovery';backup.mkdir(exist_ok=True)
    for name in ('manifest.json','state.json','heartbeat.json','corpus.jsonl'):shutil.copy2(run/name,backup/name)
    for name in ('source-indices.json','preflight.json','ben-preflight.json','launch.json','runtime-requirements.txt',
                 'RECOVERY.md','handoff.json','plan.json','environment.json','ben-recovery.json'):
        if (run/name).exists():shutil.copy2(run/name,backup/name)
    for name in ('statistics-policy.json','retirement.json','STOP','WATCHDOG_STOP'):
        if (run/name).exists():shutil.copy2(run/name,backup/name)
    for folder in ('episodes','receipts','artifacts','assets','resolved-failures'):
        for path in (run/folder).rglob('*'):
            if path.is_file() and not path.name.endswith('.tmp'):
                dest=backup/folder/path.relative_to(run/folder)
                if not dest.exists():
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    try:os.link(path,dest)
                    except OSError:shutil.copy2(path,dest)
    snapshot_runtime(run,backup)
    git(out,'add','arena')
    # Recovery deliberately contains ignored model binaries, corpus and native library.
    git(out,'add','-f','recovery')
    if git(out,'status','--porcelain').stdout.strip():
        n=json.loads((out/'arena/data.json').read_text())['completed'];git(out,'commit','-m',f'Gen5: {n} verified paired deals, common/native bidding')
    git(out,'push','-u','origin','HEAD')
    return json.loads((out/'arena/data.json').read_text())['completed']

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--publication',type=Path,required=True);p.add_argument('--once',action='store_true');a=p.parse_args()
    while not (a.run/'PUBLISH_STOP').exists():
        try:
            n=publish(a.run,a.publication)
            (a.run/'publisher-status.json').write_text(json.dumps(dict(epoch=time.time(),status='published',completed=n)))
            if a.once or n>=json.loads((a.run/'manifest.json').read_text())['target']:break
        except Exception as e:
            (a.run/'publisher-status.json').write_text(json.dumps(dict(epoch=time.time(),status='retrying',error=str(e))))
            if a.once:raise
        time.sleep(60)
