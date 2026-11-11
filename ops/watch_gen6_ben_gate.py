"""One-shot, recoverable BEN followup activation after the published lead gate.

Every check pins GitHub commits, verifies replay-index page hashes, preserves
previously observed baseline records, and counts each deal family once.
No collector is stopped until the requested native-bidding lead qualifies.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.loop_registry import sha
from bridge_harness.loop_stats import estimate
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from ops.prepare_gen6_ben_followups import prepare,load_plan
from ops.watch_gen5 import alive,free,launch,ensure_ben_servers
from ops.publish_gen5 import publish

REPOSITORY='maxschireson/Single-Dummy-Bridge'
RAW='https://raw.githubusercontent.com/'+REPOSITORY+'/'
TOKEN='GEN6_BEN_FOLLOWUPS: significant native-bidding lead; authorized one-shot transition.\n'


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.STDOUT,text=True).strip()


def request(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Gen6-BEN-followup-controller'}),timeout=30) as r:
        return r.read()


def heads():
    result={}
    for page in range(1,11):
        rows=json.loads(request(f'https://api.github.com/repos/{REPOSITORY}/branches?per_page=100&page={page}'))
        for r in rows:result[r['name']]=r['commit']['sha']
        if len(rows)<100:break
    return result


def source_records(branch,commit,gate):
    prefix=RAW+commit+'/arena/';m=json.loads(request(prefix+'manifest.json'))
    if m['generation']!=6 or m['bots']['6-256']['identity']!=gate['medium_identity']:
        raise ValueError('The medium actor changed on '+branch)
    if m['bots']['6-32']['identity']!=gate['fast_identity'] or m['bots']['ben']['identity']!=gate['ben16_identity'] or m['common_bidder']!='6-32':
        raise ValueError('The baseline or common bidder changed on '+branch)
    data=json.loads(request(prefix+'data.json'))
    if data['manifest_identity']!=m['identity']:raise ValueError('Manifest and score snapshot differ')
    path=prefix+'replays/data/'+m['identity']+'/'
    index=json.loads(request(path+'index.json'));records=list(index.get('records',[]))
    if index['cohort']!=m['identity']:raise ValueError('Replay cohort differs')
    for name in index.get('record_shards',[]):
        raw=request(path+name)
        if hashlib.sha256(raw).hexdigest()!=index['record_shard_sha256'][name]:raise ValueError('Replay index checksum mismatch')
        records.extend(json.loads(raw))
    records=[r for r in records if r['completed_epoch']<=data['generated_epoch']]
    if len(records)!=data['completed']:raise ValueError('Incomplete published batch')
    chosen=[r for r in records if r['pair']==gate['pair']]
    published=data.get('own_views',{}).get('0',{}).get('groups',{}).get(gate['pair'])
    if chosen and (not published or published['n']!=len(chosen) or published['total']!=sum(r['own_imps'] for r in chosen)):
        raise ValueError('Native score and replay totals differ')
    rows=[]
    for r in chosen:
        value=r['own_imps']
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not -24<=value<=24:raise ValueError('Invalid paired IMP value')
        rows.append(dict(family=r['family'],value=value,completed_epoch=r['completed_epoch'],cohort=m['identity'],
                         index=r['index'],episode_sha256=r['episode_sha256'],branch=branch,commit=commit))
    return rows,dict(branch=branch,commit=commit,cohort=m['identity'],records=len(rows),generated_epoch=data['generated_epoch'])


def merge_records(old,new):
    by_family={}
    for r in sorted([*old,*new],key=lambda r:(r['completed_epoch'],r['cohort'],r['index'])):
        by_family.setdefault(r['family'],r)
    return sorted(by_family.values(),key=lambda r:(r['completed_epoch'],r['cohort'],r['index']))


def evaluate(rows,gate):
    n=len(rows);stats=estimate((r['value'] for r in rows),gate['alpha']) if n>=2 else None
    return dict(qualified=bool(n>=gate['minimum_deals'] and stats and stats['informative'] and stats['low']>0),
                metric='native partnership bidding / total IMPs per board',minimum_deals=gate['minimum_deals'],
                records=n,estimate=stats,inference_note=gate['note'])


def publish_control(state,branch='arena-gen6-codex-ben-gate'):
    if not (state/'.git').exists():
        git(state,'init','-b',branch)
        git(state,'remote','add','origin','https://github.com/'+REPOSITORY+'.git')
        for key in ('user.name','user.email'):git(state,'config',key,git(ROOT,'config',key))
    files=[n for n in ('request.json','status.json','ledger.json','trigger.json','process.json','RECOVERY.md','watched-refs.json','updates.json') if (state/n).exists()]
    git(state,'add',*files)
    if git(state,'diff','--cached','--name-only'):git(state,'commit','-m','Record arena controller observations and recovery status')
    git(state,'push','-u','origin','HEAD')


def wait_for(test,description,seconds=1200):
    deadline=time.monotonic()+seconds
    while not test():
        if time.monotonic()>deadline:raise RuntimeError('Timed out: '+description)
        time.sleep(1)


def register_source(a,m,retired_revision):
    pages=a.state/'pages'
    if not (pages/'.git').exists():
        subprocess.run(['git','clone','--depth=1','--single-branch','--branch','gh-pages','https://github.com/'+REPOSITORY+'.git',str(pages)],check=True,capture_output=True)
        for key in ('user.name','user.email'):git(pages,'config',key,git(ROOT,'config',key))
    # This is the controller's disposable checkout, never the user's editing tree.
    for attempt in range(3):
        git(pages,'fetch','origin','gh-pages');git(pages,'reset','--hard','origin/gh-pages')
        path=pages/'arena/gen6-sources.json';registry=json.loads(path.read_text())
        entry=dict(key='gen6codexbenfollowups',group='gen6',generation=6,variant='6',environment='codex',
                   name='Gen 6 · BEN32 and fast/BEN16 followups',branch='arena-gen6-codex-ben-followups-feed',cohort=m['identity'])
        records=[r for r in registry['sources'] if r['key']!=entry['key']]
        for r in records:
            if r['branch']=='arena-gen6-codex-feed':r.update(retired=True,revision=retired_revision)
        registry.update(phase='ben32-and-fast-ben16',sources=[entry,*records],activation=json.loads((a.state/'trigger.json').read_text()))
        atomic_json(path,registry);git(pages,'add','arena/gen6-sources.json')
        if git(pages,'status','--porcelain'):git(pages,'commit','-m','Activate the qualified Gen6 BEN followup matches')
        try:git(pages,'push','origin','HEAD:gh-pages');return
        except subprocess.CalledProcessError:
            if attempt==2:raise


def preflight(run,pairs=None):
    from ops import gen5_runtime
    from ops.smoke_gen6 import pair_at
    from bridge_harness.corpus import load
    m=json.loads((run/'manifest.json').read_text());boards=load(run/m['corpus'])
    if pairs is None:pairs=[pair for pair in m['pair_weights'] if any(m['bots'][k].get('engine')=='ben' for k in pair.split('~'))]
    gen5_runtime.initialize_worker(str(run));reports=[]
    for pair in pairs:
        for i in range(m['target']):
            if pair_at(m,i)!=pair:continue
            r=gen5_runtime.play(str(run),m,boards[i].to_dict(),i)
            actions=[a for game in r['unique_tables'].values() for a in game['tables'][0]['actions']]
            ben=[a for a in actions if a.get('engine')=='BEN']
            if not ben:continue
            budget=next(m['bots'][k]['samples'] for k in pair.split('~') if m['bots'][k].get('engine')=='ben')
            if 'gap_cpu' in r or any('gap_forks' in record for record in r['unique_tables'].values()):
                raise ValueError('Gap capture must be disabled on BEN boards')
            if not all(a['configured_opening_lead_samples']==a['configured_play_samples']==budget for a in ben):
                raise ValueError('BEN decision metadata budget mismatch')
            reports.append(dict(pair=pair,index=i,configured_samples=budget,ben_decisions=len(ben),status='passed'))
            break
        else:raise ValueError('No playable preflight deal for '+pair)
    atomic_json(run/'ben-preflight.json',dict(manifest=m['identity'],status='passed',matches=reports));return reports


def activate(a,trigger):
    python=os.environ.get('BRIDGE_ARENA_PYTHON',sys.executable)
    phase=json.loads((a.state/'status.json').read_text())
    for name in ('statistics-policy.json','retirement.json'):
        backup=a.state/('previous-'+name)
        if not backup.exists():atomic_json(backup,json.loads((a.source/name).read_text()) if (a.source/name).exists() else None)
    if not a.run.exists():
        for name in ('STOP','WATCHDOG_STOP'):
            path=a.source/name
            if path.exists() and path.read_text()!=TOKEN:raise ValueError('Source has a different intentional stop reason')
            path.write_text(TOKEN)
        phase.update(status='draining',trigger=trigger);atomic_json(a.state/'status.json',phase);publish_control(a.state)
        wait_for(lambda:free(a.source/'.writer.lock') and free(a.source/'.watchdog.lock'),'baseline collector drain')
        (a.source/'PUBLISH_STOP').write_text(TOKEN)
        wait_for(lambda:not alive(a.source/'publisher-process.json','publish_gen5.py'),'baseline publisher exit',180)
        source_state=json.loads((a.source/'state.json').read_text())
        policy=json.loads((a.source/'statistics-policy.json').read_text()) if (a.source/'statistics-policy.json').exists() else {}
        policy.update(retired=True,target=source_state['completed'],title='Gen 6 · medium/BEN16 baseline before followups')
        atomic_json(a.source/'statistics-policy.json',policy)
        atomic_json(a.source/'retirement.json',dict(reason='Authorized BEN followup gate qualified',trigger=trigger,successor_run=str(a.run),completed=source_state['completed'],epoch=time.time()))
        subprocess.run([python,'-u','ops/publish_gen5.py','--run',str(a.source),'--publication',str(a.old_publication),'--once'],cwd=a.old_source,check=True)
        m=prepare(a.run,a.source,a.plan)
    else:
        m=json.loads((a.run/'manifest.json').read_text());verify_generation(a.run,m)
        if m['source_generation']!=json.loads((a.source/'manifest.json').read_text())['identity']:raise ValueError('Unexpected existing followup run')
    atomic_json(a.run/'gate-trigger.json',trigger)
    for name in ('runtime-requirements.txt','environment.json','ben-recovery.json'):
        if (a.source/name).exists() and not (a.run/name).exists():shutil.copy2(a.source/name,a.run/name)
    environment=json.loads((a.run/'environment.json').read_text())
    environment.update(source_commit=git(ROOT,'rev-parse','HEAD'),source_sha256=m['source_sha256'],
                       runtime_sha256=m['runtime_sha256'],manifest_identity=m['identity'],
                       publication_branch='arena-gen6-codex-ben-followups-feed',gate=trigger)
    atomic_json(a.run/'environment.json',environment)
    atomic_json(a.run/'ben-recovery.json',dict(repo='https://github.com/lorserker/ben.git',
        commit=git(a.ben_dir,'rev-parse','HEAD'),source=str(a.ben_dir),python=python,
        servers={key:dict(bot=m['bots'][key],state=str(a.ben_state/('ben-process.json' if key=='ben' else key+'-process.json')))
                 for key in ('ben','ben32')}))
    ready,_=ensure_ben_servers(a.run,m,a.ben_dir,a.ben_state)
    wait_for(lambda:ensure_ben_servers(a.run,m,a.ben_dir,a.ben_state)[0],'BEN16 and BEN32 readiness',180)
    if not (a.run/'ben-preflight.json').exists():
        subprocess.run([python,'-u',str(ROOT/'ops/watch_gen6_ben_gate.py'),'--preflight-run',str(a.run)],cwd=ROOT,check=True)
    instructions=(ROOT/'docs/gen6-ben-followups-recovery-20261111.md').read_text()
    (a.run/'RECOVERY.md').write_text(instructions);Path('/workspace/RECOVERY.md').write_text(instructions)
    if not (a.publication/'.git').exists():
        a.publication.mkdir(parents=True,exist_ok=True);git(a.publication,'init','-b','arena-gen6-codex-ben-followups-feed');git(a.publication,'remote','add','origin','https://github.com/'+REPOSITORY+'.git')
        for key in ('user.name','user.email'):git(a.publication,'config',key,git(ROOT,'config',key))
    launch_info=dict(status='starting',manifest_identity=m['identity'],run=str(a.run),source=str(ROOT),
                     source_commit=git(ROOT,'rev-parse','HEAD'),publication=str(a.publication),publication_branch='arena-gen6-codex-ben-followups-feed',trigger=trigger,epoch=time.time())
    atomic_json(a.run/'handoff.json',launch_info);atomic_json(a.run/'launch.json',launch_info)
    publish(a.run,a.publication)
    if not alive(a.run/'watchdog-process.json','watch_gen5.py') and free(a.run/'.watchdog.lock'):
        launch(a.run,'watchdog-process.json',['ops/watch_gen5.py','--run',str(a.run),'--publication',str(a.publication),'--ben-dir',str(a.ben_dir),'--ben-state',str(a.ben_state)],'watchdog.log')
    retired_revision=git(a.old_publication,'rev-parse','HEAD');register_source(a,m,retired_revision)
    wait_for(lambda:(a.run/'publisher-status.json').exists() and json.loads((a.run/'publisher-status.json').read_text()).get('completed',0)>0,'first published followup board',600)
    phase.update(status='active',followup_manifest=m['identity'],publication_branch='arena-gen6-codex-ben-followups-feed',activated_epoch=time.time());atomic_json(a.state/'status.json',phase)
    launch_info.update(status='running',watchdog_pid=json.loads((a.run/'watchdog-process.json').read_text())['pid']);atomic_json(a.run/'handoff.json',launch_info);atomic_json(a.run/'launch.json',launch_info)
    publish_control(a.state)


def main(a):
    a.state.mkdir(parents=True,exist_ok=True)
    with (a.state/'.controller.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        atomic_json(a.state/'process.json',dict(pid=os.getpid(),epoch=time.time(),source=str(ROOT)))
        plan=load_plan(a.plan);gate=plan['gate'];atomic_json(a.state/'request.json',dict(plan=plan,source=str(a.source),run=str(a.run),publication=str(a.publication),source_commit=git(ROOT,'rev-parse','HEAD')))
        plan_identity=sha(a.plan)
        protected={name:sha(ROOT/name) for name in ('ops/watch_gen6_ben_gate.py','ops/prepare_gen6_ben_followups.py',
                   'ops/watch_gen5.py','ops/publish_gen5.py','ops/gen5_runtime.py','ops/export_gen5.py')}
        ledger=json.loads((a.state/'ledger.json').read_text()) if (a.state/'ledger.json').exists() else []
        while not (a.state/'CONTROL_STOP').exists():
            try:
                if any(sha(ROOT/name)!=value for name,value in protected.items()):
                    raise ValueError('The controller source changed; inspect and explicitly restart the gate watcher')
                if sha(a.plan)!=plan_identity:raise ValueError('The followup plan changed; inspect and explicitly restart the gate watcher')
                if (a.state/'trigger.json').exists():
                    trigger=json.loads((a.state/'trigger.json').read_text());publish_control(a.state);activate(a,trigger);return
                refs=heads();new=[];snapshots=[]
                for branch in gate['required_branches']:
                    if branch not in refs:raise ValueError('Required producer missing: '+branch)
                    rows,snapshot=source_records(branch,refs[branch],gate);new.extend(rows);snapshots.append(snapshot)
                ledger=merge_records(ledger,new);result=evaluate(ledger,gate)
                atomic_json(a.state/'ledger.json',ledger)
                status=dict(status='qualified' if result['qualified'] else 'waiting_for_lead',epoch=time.time(),result=result,snapshots=snapshots)
                atomic_json(a.state/'status.json',status)
                if result['qualified']:
                    trigger=dict(epoch=time.time(),result=result,snapshots=snapshots,plan_sha256=sha(a.plan));atomic_json(a.state/'trigger.json',trigger)
                publish_control(a.state)
                print(json.dumps(status),flush=True)
                if a.once:return
                if result['qualified']:continue
            except Exception as error:
                atomic_json(a.state/'status.json',dict(status='blocked_retrying',epoch=time.time(),error=repr(error)))
                print(repr(error),flush=True)
                if a.once:raise
            time.sleep(a.interval)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--preflight-run',type=Path);p.add_argument('--preflight-only-ben32',action='store_true')
    p.add_argument('--state',type=Path,default=Path('/workspace/work/gen6-ben-gate'))
    p.add_argument('--plan',type=Path,default=ROOT/'configs/round6-ben-followups.json')
    p.add_argument('--source',type=Path,default=Path('/workspace/work/gen6-codex'))
    p.add_argument('--old-source',type=Path,default=Path('/workspace/Single-Dummy-Bridge-gen6'))
    p.add_argument('--old-publication',type=Path,default=Path('/workspace/work/gen6-codex-publication'))
    p.add_argument('--run',type=Path,default=Path('/workspace/work/gen6-ben-followups'))
    p.add_argument('--publication',type=Path,default=Path('/workspace/work/gen6-ben-followups-publication'))
    p.add_argument('--ben-dir',type=Path,default=Path('/workspace/work/ben-next-round'))
    p.add_argument('--ben-state',type=Path,default=Path('/workspace/work/round5'))
    p.add_argument('--interval',type=int,default=300);p.add_argument('--once',action='store_true');a=p.parse_args()
    if a.preflight_run:print(json.dumps(preflight(a.preflight_run,('6-256~ben32',) if a.preflight_only_ben32 else None)))
    else:main(a)
