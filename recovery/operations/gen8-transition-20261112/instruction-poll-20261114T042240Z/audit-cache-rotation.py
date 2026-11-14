import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

C=Path('/workspace/work/gen6-fast-selfplay-stream')
CASE=Path(__file__).resolve().parent
CONFIG=json.loads((C/'stream.json').read_text())
RUN=Path(CONFIG['run'])
RT=Path(CONFIG['runtime'])
PUB=Path(CONFIG['publication'])
sys.path.insert(0,str(RT))
from ops.gen5_runtime import validate

def read(p):return json.loads(p.read_text())
def git(*args):return subprocess.check_output(['git','-C',str(PUB),*args],timeout=60)
def blob(rev,path):return git('show',rev+':'+path)
def tree(rev):
    out={}
    for row in git('ls-tree','-r','-z',rev).split(b'\0'):
        if not row:continue
        meta,path=row.split(b'\t',1)
        out[path.decode()]=meta.split()[2].decode()
    return out
def gitsha(raw):return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
def fields(v,out):
    if isinstance(v,dict):
        for k,x in v.items():
            if k in out and x is not None:out[k]+=1
            fields(x,out)
    elif isinstance(v,list):
        for x in v:fields(x,out)

before='008c8d368b0fbca3005ea1a04adc05e7e7154fa9'
after='94505a462d80fea92c35fdbfcdcc807d080e0eba'
post='dcd7fb7a9066d8d3fa81b75bb6fcb41db2bdfe7a'
h=read(CASE/'health-before.json')
previous=read(CASE/'instruction-watch-before.json')
oldpid=previous['health']['pids']['collector']
newpid=h['pids']['collector']
journal=read(RUN/'last-cache-rotation.json')
assert journal['completed']==3880 and journal['previous_bytes']>2*1024**3
assert oldpid==200165 and newpid==223844 and not Path('/proc',str(oldpid)).exists()
assert h['pids']['supervisor']==previous['health']['pids']['supervisor']==68686
assert h['pids']['publisher']==previous['health']['pids']['publisher']==68688
assert not h['failure_files'] and not h['stop_files']
assert all(r['owner_pid'] in h['pids'].values() for r in h['all_lineage_locks'].values() if r['current'])
guard=C/'supervise_gen8.py'
guardhash=hashlib.sha256(guard.read_bytes()).hexdigest()
assert guardhash=='06fed99b288ac4c17ecba9d6c32aa232bcfc1412923026671fe0cd87aaf79500'
token='Gen8: intentional drain for disposable DDS cache rotation.\n'
assert blob(before,'recovery/STOP').decode()==token
states={rev:json.loads(blob(rev,'recovery/state.json')) for rev in [before,after,post]}
heartbeats={rev:json.loads(blob(rev,'recovery/heartbeat.json')) for rev in [before,after,post]}
assert states[before]['completed']==3879 and states[before]['contiguous']==3878
assert states[after]['completed']==states[after]['contiguous']==3880
assert not states[before]['failures'] and not states[after]['failures']
assert heartbeats[before]['stopping']
assert heartbeats[after]['stopping'] and heartbeats[after]['in_flight']==[3878]
assert heartbeats[post]['started_epoch']>journal['epoch']
trees={rev:tree(rev) for rev in [before,after,post]}
prior=read(C/'gen8-transition-20261112/instruction-poll-20261113T202804Z/cache-rotation-record-inventory.json')
science={p:v for p,v in prior['published_file_checks'].items() if v['category']=='scientific'}
checks={}
for path,row in science.items():
    raw=Path(row['local_path']).read_bytes()
    actual=gitsha(raw)
    assert actual==row['git_blob']==trees[before][path]==trees[after][path]==trees[post][path],path
    checks[path]=dict(git_blob=actual,local_path=row['local_path'],category='scientific')
record_checks={}
for rev in [before,after,post]:
    total=0
    for path,sha in trees[rev].items():
        if not path.startswith(('recovery/receipts/','recovery/episodes/')):continue
        local=RUN/path.removeprefix('recovery/')
        assert gitsha(local.read_bytes())==sha,path
        total+=1
        checks[path]=dict(git_blob=sha,local_path=str(local),category='record')
    assert total==2*states[rev]['completed']
    record_checks[rev]=total
m=read(RUN/'manifest.json')
records=[]
receipt_paths=sorted((RUN/'receipts').glob('*.json'))
for p in receipt_paths:
    raw=p.read_bytes();r=json.loads(raw);idx=r['index']
    ep=RUN/'episodes'/f'{idx:06d}.json.gz';sha=hashlib.sha256(ep.read_bytes()).hexdigest()
    assert r['manifest_identity']==m['identity'] and sha==r['episode_sha256']
    records.append(dict(index=idx,receipt_sha256=hashlib.sha256(raw).hexdigest(),episode_sha256=sha))
assert {r['index'] for r in records}.issuperset(range(journal['completed']))
samples=[]
for idx in range(3880,3883):
    raw=(RUN/'episodes'/f'{idx:06d}.json.gz').read_bytes();r=json.loads(gzip.decompress(raw))
    validate(r,m,idx)
    counts=dict(guess_size=0,best_share=0);fields(r,counts)
    systems={}
    for key,t in r['unique_tables'].items():
        source=t['board']['auction_source']
        assert source.startswith('systems:')
        names=source.removeprefix('systems:').split('|')
        assert len(names)==2
        systems[key]=dict(NS=names[0],EW=names[1])
    if r['pair']=='8c-32~8s-32':assert r['regimes']['common']['imps']==0
    samples.append(dict(index=idx,pair=r['pair'],gap_forks=r['gap_fork_count'],observed_fields=counts,episode_sha256=hashlib.sha256(raw).hexdigest(),receipt_hash_verified=True,replay_score_and_actor_identity_verified=True,table_systems=systems))
assert sum(r['gap_forks'] for r in samples)>0
assert all(sum(r['observed_fields'][k] for r in samples)>0 for k in ['guess_size','best_share'])
inventory=dict(receipt_snapshot_count=len(records),records=records,pre_rotation_publication=before,published_file_checks=checks)
(CASE/'cache-rotation-record-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
(CASE/'cache-rotation-journal.json').write_bytes((RUN/'last-cache-rotation.json').read_bytes())
observations=dict(before_revision=before,drain_revision=after,after_revision=post,states=states,heartbeats=heartbeats,exact_draining_stop_token=token,final_state_contiguous=3880,final_receipt_markers=sum(p.startswith('recovery/receipts/') for p in trees[after]),heartbeat_note='The final drained snapshot retains in-flight index 3878; the later post-rotation snapshot has the new collector heartbeat. No heartbeat was rewritten to imply a different lifecycle.',old_collector_exited=True,current_writer_owner=newpid)
(CASE/'cache-rotation-published-observations.json').write_text(json.dumps(observations,indent=2)+'\n')
diag=dict(type='authorized_disposable_dds_cache_rotation',journal=journal,old_collector_pid=oldpid,new_collector_pid=newpid,old_collector_exited=True,supervisor_pid_unchanged=True,publisher_pid_unchanged=True,guard_sha256=guardhash,guard_exact_stop_token=token,pre_rotation_revision=before,post_rotation_revision=post,drain_final_revision=after,drain_heartbeat=heartbeats[after],drain_completed=3880,drain_contiguous=3880,drain_established='The unchanged supervisor writes this journal only after the old collector exits and the writer lock is free. The pre-rotation publication has the exact STOP token and stopping heartbeat; the next pinned state has all 3880 contiguous receipt markers. The new collector owns the writer lock.',pre_rotation_records_verified=record_checks[before],drain_snapshot_records_verified=record_checks[after],frozen_scientific_files_verified=len(science),all_current_receipt_episode_pairs_verified=len(records),post_rotation_samples=samples,preserved_failures=True,failures_cleared=False,manual_restart=False,scientific_behavior_changed=False,manifest=m['identity'],journal_byte_count_note='Journal bytes are sampled after drain, not at peak.',recovery_stop_note='The copy-only publisher retains earlier recovery STOP bytes. Current RUN/STOP is absent and the fresh heartbeat and owner establish running state.',verified_epoch=time.time(),requires_attention=False)
(CASE/'cache-rotation-diagnosis.json').write_text(json.dumps(diag,indent=2)+'\n')
print(json.dumps({k:diag[k] for k in ['type','journal','old_collector_pid','new_collector_pid','drain_completed','pre_rotation_records_verified','drain_snapshot_records_verified','frozen_scientific_files_verified','all_current_receipt_episode_pairs_verified','requires_attention']}),flush=True)
print(json.dumps(dict(post_rotation_samples=[{k:r[k] for k in ['index','pair','gap_forks','observed_fields','replay_score_and_actor_identity_verified']} for r in samples])),flush=True)
