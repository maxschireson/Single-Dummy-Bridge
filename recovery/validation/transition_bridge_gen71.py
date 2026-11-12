"""Drain this owned Gen6 producer and prepare a separate Gen7.1 cohort."""
import fcntl
import json
from pathlib import Path
import subprocess
import time

WORK=Path('/workspace/work')
PYTHON=WORK/'bridge-venv/bin/python'
SOURCE=WORK/'bridge-gen71-source'
NEW_RUN=WORK/'bridge-gen71-19bbdce5-20261112'
PUB=WORK/'bridge-gen71-19bbdce5-publication'
STATE=WORK/'bridge-gen71-transition-state.json'
TOKEN='Authorized general arena Gen7.1 push effective2026-11-12 06:00UTC; preserve frozen Gen6 cohort.\n'

def write(path,data):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(data,indent=2)+'\n');temporary.replace(path)

def free(path):
    with path.open('a+') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);return True
        except BlockingIOError:return False

def alive(marker,script):
    try:
        pid=json.loads(marker.read_text())['pid']
        return script.encode() in Path(f'/proc/{pid}/cmdline').read_bytes()
    except (OSError,ValueError,KeyError):return False

def wait_until(check,label,timeout=600):
    deadline=time.monotonic()+timeout
    while not check():
        if time.monotonic()>=deadline:raise RuntimeError('Timed out waiting for '+label)
        time.sleep(2)

def main():
    descriptor=json.loads((WORK/'bridge-new-stream.json').read_text())
    old_run=Path(descriptor['run']);old_source=Path(descriptor['source']);old_pub=Path(descriptor['publication'])
    assert descriptor['manifest']=='19bbdce5dc29e40817e313ecf11ebb5e057364dc28ad5fc1a8d3ae0bfdff8936'
    assert not NEW_RUN.exists()
    with (WORK/'.bridge-gen71-transition.lock').open('a+') as guard:
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        transition=dict(status='draining_gen6',initial_descriptor=descriptor,new_run=str(NEW_RUN),new_source=str(SOURCE),new_publication=str(PUB),
                        branch='arena-gen71-19bbdce5-20261112-feed',source_base='56dafd6f9b733372503c4d06c9b37616f45dcc9e',
                        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=SOURCE,text=True).strip(),
                        authority='docs/gen71_2026-11-12.md: Tell all collectors; policy4.1 push effective06:00UTC; applies to general arena collectors',epoch=time.time())
        write(STATE,transition)
        descriptor['transition']=dict(status='in_progress',state=str(STATE),new_run=str(NEW_RUN))
        write(WORK/'bridge-new-stream.json',descriptor)
        assert not list((old_run/'failures').glob('*.json'))
        for name in ('WATCHDOG_STOP','STOP'):
            path=old_run/name
            if path.exists() and path.read_text()!=TOKEN:raise RuntimeError('Different intentional stop reason: '+name)
            path.write_text(TOKEN)
        print(json.dumps(dict(phase='draining_gen6')),flush=True)
        wait_until(lambda:free(old_run/'.writer.lock') and free(old_run/'.watchdog.lock'),'old writer and watchdog drain')
        (old_run/'PUBLISH_STOP').write_text(TOKEN)
        wait_until(lambda:not alive(old_run/'publisher-process.json','publish_gen5.py'),'old publisher drain')
        completed=json.loads((old_run/'state.json').read_text())['completed']
        policy=dict(retired=True,target=completed,title='Gen6 · completed stream19bbdce5 before Gen7.1')
        write(old_run/'statistics-policy.json',policy)
        retirement=dict(epoch=time.time(),completed=completed,successor=str(NEW_RUN),reason=TOKEN.strip(),raw_records_preserved=True)
        write(old_run/'retirement.json',retirement)
        # The CLI's STOP check also guards --once; call the snapshot function directly after its process has drained.
        for name in ('PUBLISH_STOP','instruction-watch.json'):
            (old_pub/'recovery'/name).write_bytes((old_run/name).read_bytes())
        code='from pathlib import Path; from ops.publish_gen5 import publish; publish(Path('+repr(str(old_run))+'),Path('+repr(str(old_pub))+'))'
        subprocess.run([str(PYTHON),'-c',code],cwd=old_source,check=True)
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=old_pub,text=True).strip()
        remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/'+descriptor['branch']],cwd=old_pub,text=True).split()[0]
        assert remote==revision
        backup_state=json.loads(subprocess.check_output(['git','show',revision+':recovery/state.json'],cwd=old_pub))
        assert backup_state['completed']==completed
        transition.update(status='preparing_gen71',old_completed=completed,old_final_revision=revision,old_retirement=retirement,epoch=time.time())
        write(STATE,transition)
        print(json.dumps(dict(phase='gen6_preserved',completed=completed,revision=revision)),flush=True)
        subprocess.run([str(PYTHON),'-u','ops/prepare_gen7_alpha.py','--source',str(old_run),'--run',str(NEW_RUN),'--plan','configs/round71-selfplay19bbdce5-compare.json'],cwd=SOURCE,check=True)
        manifest=json.loads((NEW_RUN/'manifest.json').read_text())
        assert manifest['target']+completed==25000
        assert manifest['source_generation']==descriptor['manifest']
        assert manifest['bidding_conditions']==['common','native']
        old_manifest=json.loads((old_run/'manifest.json').read_text())
        assert all(manifest['bots'][key]==old_manifest['bots'][key] for key in old_manifest['bots'])
        transition.update(status='prepared_for_preflight',new_manifest=manifest['identity'],new_target=manifest['target'],epoch=time.time())
        write(STATE,transition)
        print(json.dumps(dict(phase='prepared_for_preflight',manifest=manifest['identity'],target=manifest['target'])),flush=True)

if __name__=='__main__':main()
