"""Recoverable cutover to BEN64 plus Gen7 capture; never patch a live cohort."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops.prepare_gen6_ben_followups import prepare
from ops.publish_gen5 import publish
from ops.watch_gen5 import alive,free,launch,ensure_ben_servers
from ops.watch_gen6_ben_gate import git,wait_for,publish_control,REPOSITORY

TOKEN='Authorized BEN64 and Gen7 capture cutover, 2026-11-11.\n'


def register(a,m,revision):
    pages=a.state/'pages'
    if not (pages/'.git').exists():
        subprocess.run(['git','clone','--depth=1','--single-branch','--branch','gh-pages','https://github.com/'+REPOSITORY+'.git',str(pages)],check=True,capture_output=True)
        for key in ('user.name','user.email'):git(pages,'config',key,git(ROOT,'config',key))
    for attempt in range(4):
        # This disposable checkout has no user edits; explicit refspec avoids a stale tracking ref.
        git(pages,'fetch','origin','refs/heads/gh-pages:refs/remotes/origin/gh-pages');git(pages,'reset','--hard','origin/gh-pages')
        path=pages/'arena/gen6-sources.json';registry=json.loads(path.read_text())
        entry=dict(key='gen6codexv7capture',group='gen6',generation=6,variant='6',environment='codex',
                   name='Gen 6 · BEN64 and Gen7 capture',branch=a.branch,cohort=m['identity'])
        rows=[r for r in registry['sources'] if r['key']!=entry['key']]
        for r in rows:
            if r['cohort']==json.loads((a.source/'manifest.json').read_text())['identity']:
                r.update(retired=True,revision=revision,name='Gen 6 · completed BEN followup cohort')
        registry.update(phase='ben64-and-fast-ben16',sources=[entry,*rows],
                        ben_upgrade=dict(samples=64,medium_share=.075,fast_ben16_share=.075,status='active',epoch=time.time(),
                                         gap_fork=m['gap_fork'],replaced_samples=32))
        atomic_json(path,registry);git(pages,'add','arena/gen6-sources.json')
        if git(pages,'diff','--cached','--name-only'):git(pages,'commit','-m','Activate medium BEN64 and Gen7 capture without BEN32 dashboard results')
        try:git(pages,'push','origin','HEAD:gh-pages');return
        except subprocess.CalledProcessError:
            if attempt==3:raise


def main(a):
    a.state.mkdir(parents=True,exist_ok=True)
    with (a.state/'.cutover.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic_json(a.state/'process.json',dict(pid=os.getpid(),epoch=time.time(),source=str(ROOT)))
        atomic_json(a.state/'request.json',dict(authorized_by='Max: replace medium/BEN32 by medium/BEN64 at 7.5%; fast/BEN16 stays 7.5%; hide BEN32; apply Gen7 logging/forking instructions',
            source=str(a.source),run=str(a.run),publication=str(a.publication),branch=a.branch,source_commit=git(ROOT,'rev-parse','HEAD'),gap_branch='transfer/gen7-capture-forks-20261111'))
        def status(phase,**details):
            atomic_json(a.state/'status.json',dict(status=phase,epoch=time.time(),**details));publish_control(a.state,'arena-gen6-codex-v7-cutover')
        python=os.environ.get('BRIDGE_ARENA_PYTHON',sys.executable)
        equivalence=json.loads((a.equivalence).read_text());assert equivalence['status']=='passed'
        ben_preflight=json.loads((a.preflight/'ben-preflight.json').read_text())
        assert ben_preflight['status']=='passed' and any(r['configured_samples']==64 for r in ben_preflight['matches'])
        if not a.run.exists():
            for name in ('WATCHDOG_STOP','STOP'):
                path=a.source/name
                if path.exists() and path.read_text()!=TOKEN:raise ValueError('Different intentional stop reason')
                path.write_text(TOKEN)
            status('draining')
            wait_for(lambda:free(a.source/'.writer.lock') and free(a.source/'.watchdog.lock'),'collector drain')
            (a.source/'PUBLISH_STOP').write_text(TOKEN)
            wait_for(lambda:not alive(a.source/'publisher-process.json','publish_gen5.py'),'publisher drain',180)
            count=json.loads((a.source/'state.json').read_text())['completed']
            policy=json.loads((a.source/'statistics-policy.json').read_text()) if (a.source/'statistics-policy.json').exists() else {}
            policy.update(retired=True,target=count,title='Gen 6 · completed followups before BEN64 and Gen7 capture')
            atomic_json(a.source/'statistics-policy.json',policy)
            atomic_json(a.source/'retirement.json',dict(epoch=time.time(),completed=count,successor=str(a.run),reason=TOKEN.strip(),raw_records_preserved=True))
            subprocess.run([python,'-u','ops/publish_gen5.py','--run',str(a.source),'--publication',str(a.old_publication),'--once'],cwd=a.old_source,check=True)
            m=prepare(a.run,a.source,ROOT/'configs/round6-ben-followups.json')
        else:
            m=json.loads((a.run/'manifest.json').read_text());verify_generation(a.run,m)
        assert m['pair_weights']['6-256~ben64']==m['pair_weights']['6-32~ben']==3 and sum(m['pair_weights'].values())==40
        assert not any('ben32' in pair.split('~') for pair in m['pair_weights'])
        for name in ('runtime-requirements.txt','environment.json','gate-trigger.json'):
            if (a.source/name).exists() and not (a.run/name).exists():shutil.copy2(a.source/name,a.run/name)
        shutil.copy2(a.equivalence,a.run/'capture-equivalence.json')
        # Keep the validation cohort identity intact: it exercised the same frozen nets and BEN configs.
        shutil.copy2(a.preflight/'ben-preflight.json',a.run/'ben-preflight.json')
        ready,_=ensure_ben_servers(a.run,m,a.ben_dir,a.ben_state)
        wait_for(lambda:ensure_ben_servers(a.run,m,a.ben_dir,a.ben_state)[0],'BEN64 readiness',180)
        atomic_json(a.run/'ben-recovery.json',dict(repo='https://github.com/lorserker/ben.git',commit=git(a.ben_dir,'rev-parse','HEAD'),source=str(a.ben_dir),python=python,
            servers={k:dict(bot=m['bots'][k],state=str(a.ben_state/('ben-process.json' if k=='ben' else k+'-process.json'))) for k in ('ben','ben64')}))
        status('preflight',manifest=m['identity'])
        if not (a.run/'preflight.json').exists():
            subprocess.run([python,'-u','ops/smoke_gen6.py','--run',str(a.run),'--out',str(a.run/'preflight.json'),'--deals','2'],cwd=ROOT,check=True)
        environment=json.loads((a.run/'environment.json').read_text())
        environment.update(manifest_identity=m['identity'],source_commit=git(ROOT,'rev-parse','HEAD'),source_sha256=m['source_sha256'],runtime_sha256=m['runtime_sha256'],
                           publication_branch=a.branch,validation_cohort=json.loads((a.preflight/'manifest.json').read_text())['identity'])
        atomic_json(a.run/'environment.json',environment)
        recovery=(ROOT/'docs/gen6-v7-capture-recovery-20261111.md').read_text()
        recovery=f"Current manifest: `{m['identity']}`.\n\n"+recovery
        (a.run/'RECOVERY.md').write_text(recovery);(a.state/'RECOVERY.md').write_text(recovery);Path('/workspace/RECOVERY.md').write_text(recovery)
        handoff=dict(status='starting',manifest_identity=m['identity'],run=str(a.run),source=str(ROOT),source_commit=git(ROOT,'rev-parse','HEAD'),publication=str(a.publication),publication_branch=a.branch,epoch=time.time())
        for name in ('launch.json','handoff.json'):atomic_json(a.run/name,handoff)
        if not (a.publication/'.git').exists():
            a.publication.mkdir(parents=True,exist_ok=True);git(a.publication,'init','-b',a.branch);git(a.publication,'remote','add','origin','https://github.com/'+REPOSITORY+'.git')
            for key in ('user.name','user.email'):git(a.publication,'config',key,git(ROOT,'config',key))
        publish(a.run,a.publication)
        if not alive(a.run/'watchdog-process.json','watch_gen5.py') and free(a.run/'.watchdog.lock'):
            launch(a.run,'watchdog-process.json',['ops/watch_gen5.py','--run',str(a.run),'--publication',str(a.publication),'--ben-dir',str(a.ben_dir),'--ben-state',str(a.ben_state)],'watchdog.log')
        if not alive(a.run/'capture-report-process.json','report_gen7_capture.py'):
            launch(a.run,'capture-report-process.json',['ops/report_gen7_capture.py','--run',str(a.run),'--before',str(a.source),'--watch'],'capture-report.log')
        register(a,m,git(a.old_publication,'rev-parse','HEAD'))
        wait_for(lambda:(a.run/'publisher-status.json').exists() and json.loads((a.run/'publisher-status.json').read_text()).get('completed',0)>0,'first published capture episode',600)
        handoff.update(status='running',watchdog_pid=json.loads((a.run/'watchdog-process.json').read_text())['pid'])
        for name in ('launch.json','handoff.json'):atomic_json(a.run/name,handoff)
        atomic_json(Path('/workspace/work/current-arena.json'),handoff)
        status('active',manifest=m['identity'],handoff=handoff)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',type=Path,default=Path('/workspace/work/gen6-v7-cutover'))
    p.add_argument('--source',type=Path,default=Path('/workspace/work/gen6-ben-followups'))
    p.add_argument('--old-source',type=Path,default=Path('/workspace/Single-Dummy-Bridge-gen6-ben-followups'))
    p.add_argument('--old-publication',type=Path,default=Path('/workspace/work/gen6-ben-followups-publication'))
    p.add_argument('--run',type=Path,default=Path('/workspace/work/gen6-v7-capture'));p.add_argument('--publication',type=Path,default=Path('/workspace/work/gen6-v7-capture-publication'))
    p.add_argument('--branch',default='arena-gen6-codex-v7-capture-feed')
    p.add_argument('--preflight',type=Path,default=Path('/workspace/work/gen6-v7-ben64-preflight'))
    p.add_argument('--equivalence',type=Path,default=Path('/workspace/work/gen6-v7-capture-equivalence.json'))
    p.add_argument('--ben-dir',type=Path,default=Path('/workspace/work/ben-next-round'));p.add_argument('--ben-state',type=Path,default=Path('/workspace/work/round5'))
    main(p.parse_args())
