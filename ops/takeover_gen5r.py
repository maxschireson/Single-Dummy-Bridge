"""Drain Gen5, archive its final snapshot, then start and register Gen5R.

Run this in the collector's environment from a separate Gen5R checkout. The
original checkout, manifest and episodes remain available for rollback.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'ops'))
from bridge_harness.selfplay import atomic_json
from prepare_gen5r import prepare
from publish_gen5 import publish
from register_gen5r_report import register
from smoke_gen5r import smoke
from watch_gen5 import launch

REPO='https://github.com/maxschireson/Single-Dummy-Bridge.git'
def git(root,*args):
    return subprocess.run(['git','-C',str(root),*args],check=True,capture_output=True,text=True).stdout.strip()

def free(path):
    with path.open('a+') as f:
        try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);return True
        except BlockingIOError:return False

def wait_for(predicate,description,seconds=900):
    until=time.monotonic()+seconds
    while not predicate():
        if time.monotonic()>until:raise RuntimeError('Timed out: '+description)
        time.sleep(1)

def stop_publisher(source):
    p=source/'publisher-process.json'
    if not p.exists():return
    pid=json.loads(p.read_text())['pid'];proc=Path('/proc')/str(pid)
    try:args=(proc/'cmdline').read_bytes().decode().split('\0')
    except FileNotFoundError:return
    if not any(x.endswith('publish_gen5.py') for x in args) or str(source) not in args:
        raise RuntimeError('Publisher PID no longer matches this source run')
    os.kill(pid,signal.SIGTERM)
    wait_for(lambda:not proc.exists() or not (proc/'cmdline').read_bytes(),'old publisher exit',30)

def takeover(a):
    for name in ('source','old_publication','run','publication','pages'):
        setattr(a,name,getattr(a,name).resolve())
    if a.run.exists() or a.publication.exists():raise ValueError('New run/publication must not exist')
    if not (a.source/'manifest.json').exists():raise ValueError('Run this on the live collector host')
    if any((a.source/n).exists() for n in ('STOP','WATCHDOG_STOP')):
        raise ValueError('Source already stopped; inspect the reason before a manual handoff')
    if list((a.source/'failures').glob('*.json')):raise ValueError('Inspect source failures first')
    if git(a.pages,'status','--porcelain'):raise ValueError('Use a clean gh-pages checkout')
    if git(a.pages,'branch','--show-current')!='gh-pages':raise ValueError('Expected gh-pages checkout')
    if git(ROOT,'status','--porcelain','--untracked-files=no'):raise ValueError('Pin clean Gen5R source before launch')
    # Exercise actual artifact loaders and DDS before stopping useful collection.
    smoke(a.source,ROOT/'reports/gen5r-preflight-local.json')
    token='Authorized Gen5R takeover; preserve completed Gen5 records.\n'
    for name in ('WATCHDOG_STOP','STOP'):
        with (a.source/name).open('x') as f:f.write(token)
    wait_for(lambda:free(a.source/'.writer.lock') and free(a.source/'.watchdog.lock'),'Gen5 drain and recovery exit')
    stop_publisher(a.source)
    m=prepare(a.run,a.source)
    completed=len(list((a.source/'receipts').glob('*.json')))
    policy_path=a.source/'statistics-policy.json'
    policy=json.loads(policy_path.read_text()) if policy_path.exists() else {}
    policy.update(retired=True,target=completed,title='Gen 5 · before representative sampling')
    atomic_json(policy_path,policy)
    atomic_json(a.source/'retirement.json',dict(reason='User authorized replacement by Gen5R',completed=completed,
        successor=m['identity'],successor_run=str(a.run),epoch=time.time()))
    publish(a.source,a.old_publication)
    a.publication.mkdir(parents=True)
    git(a.publication,'init','-b','arena-gen5r-feed')
    git(a.publication,'remote','add','origin',REPO)
    # Publish the immutable empty cohort before the watchdog begins collecting.
    publish(a.run,a.publication)
    pid=launch(a.run,'watchdog-process.json',['ops/watch_gen5.py','--run',str(a.run),'--publication',str(a.publication)],'watchdog.log')
    def published_first():
        p=a.run/'publisher-status.json'
        if not p.exists():return False
        try:status=json.loads(p.read_text())
        except (OSError,ValueError):return False
        return status.get('status')=='published' and status.get('completed',0)>0
    wait_for(published_first,'first completed and published Gen5R game',600)
    files=register(a.pages,m)
    git(a.pages,'add',*[f'arena/{f}' for f in files])
    git(a.pages,'commit','-m','Show Gen5R sampling experiment and retain original Gen5 results')
    git(a.pages,'push','origin','gh-pages')
    result=dict(status='collecting-and-published',run=str(a.run),manifest_identity=m['identity'],
        publication_branch='arena-gen5r-feed',watchdog_pid=pid,allocation=m['pair_weights'],source_completed=completed,
        remaining_target=m['target'],epoch=time.time())
    atomic_json(a.run/'takeover.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name,default in [('source','/workspace/work/gen5-codex-32'),('old-publication','/workspace/work/gen5-32-publication'),
                         ('run','/workspace/work/gen5r'),('publication','/workspace/work/gen5r-publication')]:
        p.add_argument('--'+name,type=Path,default=Path(default))
    p.add_argument('--pages',type=Path,required=True)
    takeover(p.parse_args())
