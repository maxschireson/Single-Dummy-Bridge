"""Watch paired dashboard evidence; durably drain, freeze, publish and launch the next BEN allocation."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.selfplay import atomic_json
from ops.export_gen5 import stats
from ops.prepare_gen6_ben_expansion import prepare
from ops.watch_gen5 import alive,free,launch

REPO='https://github.com/maxschireson/Single-Dummy-Bridge.git'
RAW='https://raw.githubusercontent.com/maxschireson/Single-Dummy-Bridge/'
CACHE={}


def command(args,cwd=None):
    return subprocess.check_output(list(map(str,args)),cwd=cwd,text=True,stderr=subprocess.STDOUT).strip()


def fetch(path,checksum=None):
    if checksum and checksum in CACHE:return CACHE[checksum]
    with urlopen(RAW+path,timeout=30) as response:raw=response.read()
    if checksum and hashlib.sha256(raw).hexdigest()!=checksum:raise ValueError('Replay shard hash mismatch')
    value=json.loads(raw)
    if checksum:CACHE[checksum]=value
    return value


def sources_from_script(script):
    out=[]
    for line in script.splitlines():
        if "group:'gen6'" not in line:continue
        fields=dict(re.findall(r"(\w+):'([^']*)'",line))
        if fields.get('branch') and fields.get('cohort'):
            out.append(fields)
    if not out:raise ValueError('No registered Gen6 sources')
    return out


def paired_evidence(snapshots,condition='total'):
    rows=[]
    for source,data,records in snapshots:
        if data['manifest_identity']!=source['cohort']:raise ValueError('Source cohort changed')
        if len(records)!=data['completed']:raise ValueError('Incomplete score/replay snapshot')
        for r in records:
            if r['pair'] not in ('6-256~ben','ben~6-256'):continue
            if r['completed_epoch']>data['generated_epoch']:continue
            if not r.get('family'):raise ValueError('Missing family identity')
            field='own_imps' if condition=='total' else 'imps'
            value=r[field]
            if not isinstance(value,(int,float)):raise ValueError('Missing paired result')
            if r['pair'].startswith('ben~'):value=-value
            rows.append((r['completed_epoch'],source['cohort'],r['index'],r['family'],value))
    seen=set();values=[]
    for _,_,_,family,value in sorted(rows):
        if family in seen:continue
        seen.add(family);values.append(value)
    s=stats(values)
    return dict(pair='6-256~ben',condition=condition,confidence=.95,method='Paired Student-t interval, evaluated repeatedly as on dashboard; exploratory, no sequential correction',**s,
                significant=bool(s['n']>=2 and s['ci'] and s['ci'][0]>0),deduplicated_families=len(seen))


def evidence(condition):
    lines=command(['git','ls-remote',REPO,'refs/heads/*']).splitlines()
    refs={ref.removeprefix('refs/heads/'):sha for sha,ref in (line.split() for line in lines)}
    with urlopen(RAW+refs['gh-pages']+'/arena/reporting.js',timeout=30) as r:script=r.read().decode()
    sources=sources_from_script(script);snapshots=[];provenance=[]
    for source in sources:
        revision=source.get('revision') or refs[source['branch']]
        prefix=revision+'/arena/'
        data=fetch(prefix+'data.json')
        if data['manifest_identity']!=source['cohort']:raise ValueError('Registered cohort and feed disagree')
        index=fetch(prefix+'replays/data/'+source['cohort']+'/index.json')
        records=list(index.get('records',[]))
        for shard in index.get('record_shards',[]):
            digest=index['record_shard_sha256'][shard]
            records.extend(fetch(prefix+'replays/data/'+source['cohort']+'/'+shard,digest))
        snapshots.append((source,data,records));provenance.append(dict(branch=source['branch'],revision=revision,cohort=source['cohort']))
    return dict(paired_evidence(snapshots,condition),sources=provenance,checked_epoch=time.time())


def initialize_publication(path,branch):
    path=Path(path)
    if (path/'.git').exists():return
    path.mkdir(parents=True)
    command(['git','init','-b',branch,path]);command(['git','-C',path,'remote','add','origin',REPO])
    command(['git','-C',path,'config','user.name','Codex']);command(['git','-C',path,'config','user.email','codex@openai.com'])


def dashboard_patch(pages,old,new,revision,branch):
    pages=Path(pages);rpath=pages/'arena/reporting.js';r=rpath.read_text()
    # Replace this collector's live source; retain its completed cohort as a frozen source.
    lines=r.splitlines(keepends=True);found=False
    for i,line in enumerate(lines):
        if "key:'gen6independent'" not in line:continue
        if new['identity'] in line:return
        if old['identity'] not in line:raise ValueError('Dashboard live source is a different cohort')
        retained=line.replace("key:'gen6independent'","key:'gen6ben16completed'").replace("group:'gen6',","group:'gen6',retired:true,revision:'"+revision+"',").replace("name:'Gen 6 · independent collector'","name:'Gen 6 · completed medium vs BEN16 cohort'")
        live=line.replace(old['identity'],new['identity']).replace("branch:'arena-gen6-medium-ben-feed'","branch:'"+branch+"'")
        lines[i]=live+retained;found=True;break
    if not found:raise ValueError('Independent dashboard source is missing')
    r=''.join(lines)
    if "'ben32':" not in r:
        r=r.replace(' const labels={'," const labels={'ben32':'BEN (32)',",1)
        r=r.replace("order=['6-32'","order=['ben32','6-32'",1)
    # Re-open fast/BEN16 only for the expansion cohort, preserving prior exclusions.
    r=r.replace("const archivedPair=p=>normalizePair(p).pair==='6-32~ben';", "const archivedPair=(p,source)=>normalizePair(p).pair==='6-32~ben'&&source?.cohort!=='"+new['identity']+"';")
    r=r.replace('archivedPair(r.pair)||','archivedPair(r.pair,source)||')
    r=r.replace('records=input.index?.records?.filter(r=>!archivedPair(r.pair)&&','records=input.index?.records?.filter(r=>!archivedPair(r.pair,input.source)&&')
    r=r.replace('input.index?.records?.some(r=>archivedPair(r.pair))','input.index?.records?.some(r=>archivedPair(r.pair,input.source))')
    r=r.replace('!archivedPair(r.pair)&&','!archivedPair(r.pair,x.source)&&')
    rpath.write_text(r)
    cpath=pages/'arena/replays/common.js';c=cpath.read_text()
    if branch not in c:c=c.replace('const urls=[',"const urls=['"+RAW+branch+"/arena/replays/catalog.json',",1)
    if "'ben32':" not in c:c=c.replace('const labels = {',"const labels = {'ben32':'BEN (32)',",1)
    cpath.write_text(c)


def publish_dashboard(config,old,new,revision):
    stamp=str(time.time_ns());pages=Path(config['control'])/('dashboard-'+stamp)
    command(['git','clone','--depth','1','--filter=blob:none','--sparse','--branch','gh-pages',REPO,pages])
    command(['git','-C',pages,'sparse-checkout','set','arena'])
    dashboard_patch(pages,old,new,revision,config['branch'])
    command(['node','--check',pages/'arena/reporting.js'])
    command(['git','-C',pages,'config','user.name','Codex']);command(['git','-C',pages,'config','user.email','codex@openai.com'])
    command(['git','-C',pages,'add','arena/reporting.js','arena/replays/common.js'])
    if command(['git','-C',pages,'status','--porcelain']):
        command(['git','-C',pages,'commit','-m','Expand BEN allocation after significant Gen6 medium lead; retain completed evidence'])
        command(['git','-C',pages,'push','origin','HEAD:gh-pages'])
    return command(['git','-C',pages,'rev-parse','HEAD'])


def tick(config,state):
    control=Path(config['control']);source=Path(config['source']);target=Path(config['target'])
    old=json.loads((source/'manifest.json').read_text())
    phase=state.get('phase','watching')
    if phase=='watching':
        result=evidence(config['condition']);state.update(evidence=result,checked_epoch=time.time())
        if not result['significant']:return state
        atomic_json(control/'trigger.json',result);state.update(phase='draining',trigger=result)
        atomic_json(control/'state.json',state)
    if state['phase']=='draining':
        (source/'WATCHDOG_STOP').write_text('Significant medium/BEN16 lead: stop allocation and expand BEN budgets\n')
        (source/'STOP').write_text('Drain for significance-triggered allocation\n')
        if not free(source/'.writer.lock'):return state
        (source/'PUBLISH_STOP').write_text('Freeze completed medium/BEN16 evidence\n')
        if alive(source/'publisher-process.json','publish_gen5.py'):return state
        completed=json.loads((source/'state.json').read_text())['completed']
        atomic_json(source/'statistics-policy.json',dict(retired=True,target=completed,title='Gen6 completed medium/BEN16 evidence'))
        command([config['python'],'-c','from pathlib import Path; import sys; from ops.publish_gen5 import publish; publish(Path(sys.argv[1]),Path(sys.argv[2]))',source,config['source_publication']],cwd=config['source_checkout'])
        state.update(phase='preparing',source_revision=command(['git','-C',config['source_publication'],'rev-parse','HEAD']))
        atomic_json(control/'state.json',state)
    if state['phase']=='preparing':
        if target.exists():
            m=json.loads((target/'manifest.json').read_text())
            if m.get('source_generation')!=old['identity']:raise ValueError('Target belongs to a different source')
        else:m=prepare(target,source,config['profile32'],state['trigger'])
        for marker in ('ben-process.json','ben-8088-process.json'):
            origin=source/marker if (source/marker).exists() else control/marker
            if origin.exists():(target/marker).write_bytes(origin.read_bytes())
        initialize_publication(config['publication'],config['branch'])
        command([config['python'],ROOT/'ops/publish_gen5.py','--run',target,'--publication',config['publication'],'--once'],cwd=ROOT)
        state.update(phase='dashboard',manifest_identity=m['identity']);atomic_json(control/'state.json',state)
    if state['phase']=='dashboard':
        m=json.loads((target/'manifest.json').read_text())
        state['dashboard_commit']=publish_dashboard(config,old,m,state['source_revision'])
        state['phase']='launching';atomic_json(control/'state.json',state)
    if state['phase']=='launching':
        if not alive(target/'watchdog-process.json','watch_gen5.py'):
            launch(target,'watchdog-process.json',['ops/watch_gen5.py','--run',str(target),'--publication',config['publication'],'--ben-dir',config['ben_dir'],'--ben-state',str(target)],'watchdog.log')
        state.update(phase='switched',switched_epoch=time.time())
    return state


def main(config,once=False):
    control=Path(config['control']);control.mkdir(parents=True,exist_ok=True)
    with (control/'.controller.lock').open('a+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=json.loads((control/'state.json').read_text()) if (control/'state.json').exists() else {'phase':'watching'}
        while not (control/'STOP').exists():
            try:
                state=tick(config,state);state.pop('error',None)
            except Exception as e:state.update(error=repr(e),error_epoch=time.time())
            atomic_json(control/'state.json',state)
            policy=dict(state,rule=config['condition'],freed_allocation=.15,new_matches={'6-256~ben32':.075,'6-32~ben':.075})
            atomic_json(Path(config['source_publication'])/'arena/ben-allocation-policy.json',policy)
            if (Path(config['publication'])/'arena').exists():atomic_json(Path(config['publication'])/'arena/ben-allocation-policy.json',policy)
            if once or state.get('phase')=='switched':break
            time.sleep(60)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--once',action='store_true');a=p.parse_args();main(json.loads(a.config.read_text()),a.once)
