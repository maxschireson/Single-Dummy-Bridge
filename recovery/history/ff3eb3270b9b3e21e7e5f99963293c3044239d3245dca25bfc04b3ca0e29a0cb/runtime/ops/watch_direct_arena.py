"""Five-minute local watchdog and twelve rolling direct-match report views.

Operational only: no changes to frozen collection/training source or models.
OS locks prevent duplicate watchdogs, supervisors and writers. A stopped process
is recoverable; a held lock is never overridden or killed by this watchdog.
"""
import argparse
from contextlib import contextmanager, ExitStack
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.improvement import read
from bridge_harness.selfplay import atomic_json
from bridge_harness.mixed_arena import verify_generation
from ops.mixed_generation import receipts


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield f


def lock_state(path):
    try:
        with lock(path): return 'free'
    except BlockingIOError: return 'held'


def report_views(rows, manifest, now):
    reports={}
    for pair in ('AB','AC','BC'):
        all_rows=[r for r in rows if r['pair']==pair]
        for minutes in (5,15,30,60):
            selected=[r for r in all_rows if now-minutes*60 < r['completed_epoch'] <= now]
            elapsed=min(minutes*60,max(0,now-manifest['created_epoch']))
            n=len(selected);total=sum(r['imps'] for r in selected)
            reports[f'{pair}-{minutes}m']=dict(pair=pair,window_minutes=minutes,as_of_epoch=now,
                window_start_epoch=now-minutes*60,coverage_seconds=elapsed,
                full_window=elapsed>=minutes*60,completed_pairs=n,
                pairs_per_hour=n*3600/elapsed if elapsed else None,
                net_imps=total,imps_per_pair=total/n if n else None,
                wins=sum(r['imps']>0 for r in selected),losses=sum(r['imps']<0 for r in selected),
                ties=sum(r['imps']==0 for r in selected),cumulative_pairs=len(all_rows),
                cumulative_imps=sum(r['imps'] for r in all_rows),
                note='Completion-time window including downtime, not independent validation or active-CPU throughput. Different windows overlap.')
    return reports


def transient_failures(paths):
    # Never erase or automatically retry integrity, model, replay or application errors.
    for p in paths:
        trace=read(p).get('traceback','')
        if 'concurrent.futures.process.BrokenProcessPool:' not in trace:
            return False
    return True


def launch_settings(run,workers):
    launcher='ops/diagnostic_supervisor.py'
    path=run/'telemetry-ramp.json'
    if path.exists():
        settings=read(path)
        if settings.get('status')=='running-verified':
            launcher=settings.get('launcher',launcher);workers=int(settings.get('workers',workers))
    if launcher not in ('ops/diagnostic_supervisor.py','ops/telemetry_supervisor.py','ops/independent_supervisor.py'):
        raise ValueError('Unknown operational launcher')
    if not 1<=workers<=8:raise ValueError('Invalid operational worker count')
    return launcher,workers


def launch(run,workers):
    launcher,workers=launch_settings(run,workers)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with (run/'supervisor.log').open('a') as log:
        child=subprocess.Popen([sys.executable,'-u',str(ROOT/launcher),
            'supervise','--run',str(run),'--seconds','60','--workers',str(workers)],
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    return child


def recover(run, manifest, workers, history, launcher=launch):
    # Recheck locks atomically for investigation. Launcher itself must acquire both
    # production locks after release; losing that race cannot create a second writer.
    with ExitStack() as stack:
        for name in ('.supervisor.lock','.writer.lock'):
            stack.enter_context(lock(run/name))
        if (run/'STOP').exists(): return dict(action='intentional-stop')
        verify_generation(run,manifest)
        rows=receipts(run,manifest,audit=True)
        before=len(rows)
        if before>=manifest['target']: return dict(action='collection-complete')
        failures=sorted((run/'failures').glob('*.json'))
        if not transient_failures(failures):
            return dict(action='blocked-unrecognized-failure',failures=[str(p) for p in failures])
        done={r['index'] for r in rows}
        missing=next(i for i in range(manifest['target']) if i not in done)
        attempts=read(history) if history.exists() else {}
        key=f"{manifest['identity']}:{missing}"
        if attempts.get(key,0)>=3:
            return dict(action='blocked-repeated-no-progress',next_index=missing,attempts=attempts[key])
        archive=run/'failure-history'/f'watchdog-{time.time_ns()}'
        archive.mkdir(parents=True)
        for p in failures:p.rename(archive/p.name)
        atomic_json(archive/'investigation.json',dict(epoch=time.time(),audited=before,next_index=missing,
            cause='Abrupt worker loss' if failures else 'No supervisor or writer holds lock',
            underlying_cause='unknown',source_models_verified=True,
            action='Resume missing indices; preserve all completed records'))
        attempts[key]=attempts.get(key,0)+1;atomic_json(history,attempts)
    if (run/'STOP').exists(): return dict(action='intentional-stop')
    child=launcher(run,workers)
    return dict(action='restarted-awaiting-progress',before=before,next_index=missing,
        child_pid=child.pid,workers=workers,attempt=attempts[key])


def check(pointer, workers=2, launcher=launch):
    home=pointer.parent; output=home/'watchdog';output.mkdir(exist_ok=True)
    current=read(pointer);run=Path(current['run']);manifest=read(run/'manifest.json')
    launcher_name,workers=launch_settings(run,workers)
    if manifest.get('protocol')!='direct-pairs-v1': raise ValueError('Unexpected protocol; do not revive legacy collector')
    # Read atomic receipts only: report generation must not repair/write episodes.
    rows=[read(p) for p in sorted((run/'receipts').glob('*.json'))]
    if any(r['manifest_identity']!=manifest['identity'] for r in rows):raise ValueError('Receipt identity mismatch')
    if len({r['index'] for r in rows})!=len(rows) or len({r['family'] for r in rows})!=len(rows):
        raise ValueError('Duplicate committed receipt')
    now=time.time();views=report_views(rows,manifest,now)
    from ops.summarize_arena_health import summarize as health_summary
    atomic_json(output/'diagnostics-summary.json',health_summary(run))
    for name,report in views.items():atomic_json(output/'reports'/f'{name}.json',report)
    atomic_json(output/'reports.json',dict(run=str(run),manifest_identity=manifest['identity'],epoch=now,reports=views))
    locks={name:lock_state(run/name) for name in ('.supervisor.lock','.writer.lock')}
    last=max((r['completed_epoch'] for r in rows),default=manifest['created_epoch'])
    state=dict(epoch=now,run=str(run),manifest_identity=manifest['identity'],completed=len(rows),
        batch_completed=len(rows)+manifest.get('legacy_completed',0),target=manifest['target'],
        locks=locks,last_commit_age_seconds=now-last,reports=12,workers=workers,
        interval_seconds=300,pid=os.getpid(),next_check_epoch=now+300,launcher=launcher_name)
    if (run/'STOP').exists():state['action']='intentional-stop'
    elif len(rows)>=manifest['target']:state['action']='collection-complete-transition-owned-by-supervisor-or-monitors'
    elif 'held' in locks.values():state['action']='running' if now-last<600 else 'held-lock-no-recent-progress-investigate'
    else:
        try:state.update(recover(run,manifest,workers,output/'recovery-attempts.json',launcher))
        except BlockingIOError:state['action']='another-owner-acquired-lock'
    atomic_json(output/'status.json',state)
    with (output/'history.jsonl').open('a') as f:f.write(json.dumps(state)+'\n')
    return state


def verify_restart(pointer, state, timeout=120):
    run=Path(state['run']);deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        current=read(pointer)
        if current['run']!=str(run):return dict(state,action='advanced-to-successor')
        count=len(list((run/'receipts').glob('*.json')))
        if count>state['before']:
            return dict(state,action='restart-progress-verified',verified_epoch=time.time(),completed=count,
                locks={n:lock_state(run/n) for n in ('.supervisor.lock','.writer.lock')},
                batch_completed=count+read(run/'manifest.json').get('legacy_completed',0))
        if (run/'STOP').exists():return dict(state,action='intentional-stop')
        time.sleep(2)
    return dict(state,action='restart-no-progress-yet',checked_epoch=time.time())


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pointer',type=Path,required=True)
    p.add_argument('--workers',type=int,default=2);p.add_argument('--once',action='store_true')
    args=p.parse_args();pointer=args.pointer.resolve();home=pointer.parent/'watchdog';home.mkdir(exist_ok=True)
    with lock(home/'.watchdog.lock'):
        while not (home/'STOP').exists():
            started=time.monotonic()
            try:
                state=check(pointer,args.workers)
                if state['action']=='restarted-awaiting-progress':
                    state=verify_restart(pointer,state);atomic_json(home/'status.json',state)
                    atomic_json(Path(state['run'])/'watchdog-recovery-latest.json',state)
                print(json.dumps(state),flush=True)
            except Exception:
                state=dict(epoch=time.time(),action='watchdog-check-error',traceback=traceback.format_exc(),pid=os.getpid())
                atomic_json(home/'status.json',state);print(json.dumps(state),flush=True)
            if args.once:return
            # Short sleeps keep STOP responsive, without extra recovery/report polls.
            while time.monotonic()-started<300 and not (home/'STOP').exists():time.sleep(2)

if __name__=='__main__':main()
