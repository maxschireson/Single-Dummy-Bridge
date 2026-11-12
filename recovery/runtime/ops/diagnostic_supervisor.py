"""Operational arena wrapper: resource evidence and one-minute worker recycling.

Frozen play, scoring, models, and corpus are unchanged. A new process pool is
created each bounded collection slice, preventing unbounded per-worker buildup.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def read_optional(path):
    try:return Path(path).read_text()
    except OSError:return None


def memory_snapshot():
    values={}
    for line in (read_optional('/proc/meminfo') or '').splitlines():
        key,_,value=line.partition(':')
        if key in ('MemTotal','MemAvailable','MemFree','Cached','SwapFree','SwapTotal'):
            values[key+'_kb']=int(value.split()[0])
    for line in (read_optional('/proc/vmstat') or '').splitlines():
        key,value=line.split()
        if key in ('oom_kill','pgmajfault') or key.startswith('allocstall'):values[key]=int(value)
    values['cgroup_metrics_available']=Path('/sys/fs/cgroup/memory.events').exists()
    if values['cgroup_metrics_available']:values['cgroup_memory_events']=read_optional('/sys/fs/cgroup/memory.events')
    return values


def process_snapshot(pid):
    result={'pid':pid}
    data=read_optional(f'/proc/{pid}/status')
    if data is None:return dict(result,visible=False)
    for line in data.splitlines():
        key,_,value=line.partition(':')
        if key in ('VmRSS','VmHWM','VmSize','Threads','State','Cpus_allowed_list','voluntary_ctxt_switches','nonvoluntary_ctxt_switches'):
            result[key]=value.strip()
    stat=read_optional(f'/proc/{pid}/stat')
    if stat:
        fields=stat.rsplit(')',1)[-1].split()
        result['cpu_ticks']=int(fields[11])+int(fields[12])
    return result


class Recorder:
    def __init__(self,run,kind):
        self.run=Path(run);self.kind=kind;self.path=self.run/'diagnostics'/f'{kind}-{time.time_ns()}-{os.getpid()}.jsonl'
        self.path.parent.mkdir(exist_ok=True);self.mutex=threading.Lock()
    def emit(self,event,**details):
        with self.mutex, self.path.open('a') as f:
            f.write(json.dumps(dict(epoch=time.time(),event=event,parent_pid=os.getpid(),**details))+'\n')


class DiagnosticPool(concurrent.futures.ProcessPoolExecutor):
    run=None
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.recorder=Recorder(self.run,'pool');self.known={};self.reported=set();self.stop_event=threading.Event()
        self.recorder.emit('pool-start',max_workers=self._max_workers,resources=memory_snapshot())
        self.monitor=threading.Thread(target=self.observe,daemon=True);self.monitor.start()
    def sample(self,resources=False):
        self.known.update(dict(self._processes or {}))
        for pid,process in list(self.known.items()):
            code=process.exitcode
            if code is not None and pid not in self.reported:
                self.reported.add(pid)
                self.recorder.emit('worker-exit',pid=pid,exitcode=code,
                    signal=signal.Signals(-code).name if code<0 else None,
                    resources=memory_snapshot(),note='Exit signal is evidence, not by itself proof of OOM; peer exits may be cleanup.')
        if resources:self.recorder.emit('resources',resources=memory_snapshot(),parent=process_snapshot(os.getpid()),workers=[process_snapshot(p) for p in self.known if p not in self.reported])
    def observe(self):
        tick=0
        while not self.stop_event.wait(.25):
            try:self.sample(resources=tick%20==0)
            except Exception as e:self.recorder.emit('observer-error',error=repr(e))
            tick+=1
    def shutdown(self,*args,**kwargs):
        try:
            self.sample(resources=True)
            return super().shutdown(*args,**kwargs)
        finally:
            self.stop_event.set();self.monitor.join(timeout=2);self.sample(resources=True)
            self.recorder.emit('pool-end')


def main():
    import ops.mixed_generation as runtime
    import ops.supervise_mixed as supervisor
    run=Path(sys.argv[sys.argv.index('--run')+1]).resolve()
    record=Recorder(run,'supervisor' if sys.argv[1]=='supervise' else 'collector')
    record.emit('start',mode=sys.argv[1],resources=memory_snapshot(),slice_seconds=60)
    # Clamp pool lifetime operationally, without editing the pinned collector.
    if '--seconds' in sys.argv:sys.argv[sys.argv.index('--seconds')+1]='60'
    DiagnosticPool.run=run;runtime.ProcessPoolExecutor=DiagnosticPool
    original=supervisor.command
    def command(args,root,timeout):
        if len(args)>1 and args[1]=='ops/mixed_generation.py':
            args=[args[0],'ops/diagnostic_supervisor.py',*args[2:]]
        record.emit('child-launch',program=args[1],mode=args[2] if len(args)>2 else None,resources=memory_snapshot())
        try:return original(args,root,timeout)
        except BaseException as e:
            record.emit('child-failure',error=repr(e),resources=memory_snapshot());raise
        finally:record.emit('child-finished',resources=memory_snapshot())
    runtime.supervised_command=command
    attempts={}
    while True:
        try:
            runtime.main()
            break
        except BlockingIOError:
            record.emit('ownership-transferred');break
        except Exception as e:
            record.emit('exit-error',error=repr(e),resources=memory_snapshot())
            if sys.argv[1]!='supervise' or (run/'STOP').exists():raise
            from contextlib import ExitStack
            from ops.watch_direct_arena import lock, transient_failures
            from bridge_harness.improvement import read
            from bridge_harness.mixed_arena import verify_generation
            from bridge_harness.selfplay import atomic_json
            # Resume only recognized process loss, after all production locks release.
            try:
                with ExitStack() as stack:
                    for n in ('.supervisor.lock','.writer.lock'):stack.enter_context(lock(run/n))
                    failures=list((run/'failures').glob('*.json'))
                    if not failures or not transient_failures(failures):raise e
                    m=read(run/'manifest.json');verify_generation(run,m)
                    rows=runtime.receipts(run,m,audit=True);done={r['index'] for r in rows}
                    missing=next((i for i in range(m['target']) if i not in done),m['target'])
                    attempts[missing]=attempts.get(missing,0)+1
                    if attempts[missing]>3:raise RuntimeError('Repeated process loss without progress') from e
                    archive=run/'failure-history'/f'diagnostic-{time.time_ns()}';archive.mkdir(parents=True)
                    for f in failures:f.rename(archive/f.name)
                    atomic_json(archive/'investigation.json',dict(epoch=time.time(),audited=len(rows),
                        next_index=missing,attempt=attempts[missing],resources=memory_snapshot(),
                        diagnostic_log=str(record.path),cause='BrokenProcessPool; inspect worker exit evidence'))
                    record.emit('automatic-recovery',completed=len(rows),next_index=missing,resources=memory_snapshot())
            except BlockingIOError:
                record.emit('ownership-transferred');break
            time.sleep(5)
    record.emit('exit',resources=memory_snapshot())

if __name__=='__main__':main()
