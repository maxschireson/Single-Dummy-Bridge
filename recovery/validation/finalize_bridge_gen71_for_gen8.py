import json,time,subprocess,fcntl
from pathlib import Path

work=Path('/workspace/work');sp=work/'bridge-gen8-transition-state.json';state=json.loads(sp.read_text());d=state['initial_descriptor'];run=Path(d['run']);pub=Path(d['publication']);source=Path(d['source'])
def write(path,value):
    tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
def alive(name):
    p=Path('/proc')/str(json.loads((run/name).read_text())['pid'])/'cmdline'
    return p.exists() and bool(p.read_bytes())
assert state['status']=='draining_gen71' and not alive('process.json') and not list((run/'failures').glob('*.json'))
for name in ('.writer.lock','.watchdog.lock'):
    with (run/name).open('rb') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
deadline=time.monotonic()+120
while alive('publisher-process.json'):
    if time.monotonic()>deadline:raise RuntimeError('Publisher has not drained')
    time.sleep(2)
n=json.loads((run/'state.json').read_text())['completed'];assert n==2189
assert len(list((run/'receipts').glob('*.json')))==len(list((run/'episodes').glob('*.json.gz')))==n
write(run/'statistics-policy.json',dict(retired=True,target=n,title='Gen7.1 comparison · completed stream19bbdce5 before Gen8'))
write(run/'retirement.json',dict(epoch=time.time(),completed=n,successor=state['new_run'],reason=state['authority'],raw_records_preserved=True,restart_authorized=False))
watch=json.loads((run/'instruction-watch.json').read_text());watch.update(previous_checked_epoch=watch['checked_epoch'],checked_epoch=time.time(),coordination_revision='ae9f949b88e4ff71ba153d922c4d796a2b7c227c',coordination_blob='9704fdc6f56e1703766e18c0f9a7d8315ef3b90d',registry_blob='33f3708f9bdfc51d5a8eea0549d2cb5ac600a397',action='drained_gen71_for_authorized_gen8',status='permanently_retired_for_gen8',current_completed=n,gen71_promotion_gate='Superseded by Max16:11 explicit Gen8 arena cutover; no Gen7.1 self-play transition',transition_state=str(sp))
watch['handled_instructions'].append(dict(instruction='All collectors including19bbdce5 switch to authorized Gen8 plan792c4cb with the34092-family union.',authority='Max16:11 and operator16:24, box/coordination ae9f949b88e4ff71ba153d922c4d796a2b7c227c',action='Drained in-flight work; disabled watchdog and publisher; preserved2189 Gen7.1 completed families; separate successor preparation follows.'))
write(run/'instruction-watch.json',watch)
for name in ('PUBLISH_STOP','instruction-watch.json'):(pub/'recovery'/name).write_bytes((run/name).read_bytes())
subprocess.run(['git','-C',str(pub),'config','http.postBuffer','524288000'],check=True)
code='from pathlib import Path;from ops.publish_gen5 import publish;publish(Path('+repr(str(run))+'),Path('+repr(str(pub))+'))'
subprocess.run([str(work/'bridge-venv/bin/python'),'-c',code],cwd=source,check=True)
rev=subprocess.check_output(['git','-C',str(pub),'rev-parse','HEAD'],text=True).strip();remote=subprocess.check_output(['git','-C',str(pub),'ls-remote','origin','refs/heads/'+d['branch']],text=True).split()[0];assert remote==rev
archived=json.loads(subprocess.check_output(['git','-C',str(pub),'show',rev+':recovery/state.json'],text=True));assert archived['completed']==n
state.update(status='gen71_archived',old_completed=n,old_final_revision=rev,new_target=d['target']-n,total_predecessor_completed=6775+n,epoch=time.time());write(sp,state)
print(json.dumps(dict(status=state['status'],completed=n,revision=rev,new_target=state['new_target'])),flush=True)
