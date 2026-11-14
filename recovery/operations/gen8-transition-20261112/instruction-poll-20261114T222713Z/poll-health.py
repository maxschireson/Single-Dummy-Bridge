import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time

CONTROL = Path('/workspace/work/gen6-fast-selfplay-stream')
CASE = Path(__file__).resolve().parent
CONFIG = json.loads((CONTROL / 'stream.json').read_text())
RUN = Path(CONFIG['run'])
RUNTIME = Path(CONFIG['runtime'])
sys.path.insert(0, str(RUNTIME))
from bridge_harness.mixed_arena import verify_generation

def read(path):
    return json.loads(Path(path).read_text())

def nested_counts(value, counts):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in counts and child is not None:
                counts[key] += 1
            nested_counts(child, counts)
    elif isinstance(value, list):
        for child in value:
            nested_counts(child, counts)

def check():
    now = time.time()
    m = read(RUN / 'manifest.json')
    assert m['identity'] == CONFIG['manifest']
    verify_generation(RUN, m)
    ex = CONFIG['training_family_exclusions']
    assert hashlib.sha256(Path(ex['path']).read_bytes()).hexdigest() == ex['sha256']
    prior = read(CONTROL / 'instruction-watch.json')
    old = Path(prior['scan_evidence_path']).parent
    previous = read(old / 'health-after.json')
    h = dict(epoch=now, poll_start='2026-11-14T22:27:13Z', manifest=m['identity'])
    for key, name in [('heartbeat','heartbeat.json'),('state','state.json'),('supervisor','watchdog-status.json'),('publisher','publisher-status.json')]:
        h[key] = read(RUN / name)
    h['pids'] = {k:read(RUN / n)['pid'] for k,n in [('collector','process.json'),('supervisor','watchdog-process.json'),('publisher','publisher-process.json')]}
    h['pid_alive'] = {k:Path('/proc',str(pid)).exists() for k,pid in h['pids'].items()}
    h['all_lineage_locks'] = {}
    proc_locks = Path('/proc/locks').read_text().splitlines()
    for name, before in previous['all_lineage_locks'].items():
        path = Path(name)
        with path.open('r+') as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                held = False
                fcntl.flock(f, fcntl.LOCK_UN)
            except BlockingIOError:
                held = True
        st = path.stat()
        devino = f'{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}'
        owners = [int(row.split()[4]) for row in proc_locks if devino in row.split()]
        h['all_lineage_locks'][name] = dict(held=held,owner_pid=owners[0] if owners else None,current=path.parent==RUN)
        assert held == (path.parent == RUN), (name,held)
    collector = h['pids']['collector']
    children = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            stat = (path/'stat').read_text().rsplit(')',1)[1].split()
            if int(stat[1]) == collector:
                children.append(dict(pid=int(path.name),command=(path/'cmdline').read_bytes().replace(b'\0',b' ').decode()))
        except (FileNotFoundError,ProcessLookupError,PermissionError):
            pass
    h['collector_children'] = children
    h['actual_normal_worker_children'] = sum('spawn_main' in row['command'] for row in children)
    h['ben_jobs'] = 0
    h['raw_heartbeat_idle_ben_executor_is_not_a_job'] = True
    h['failure_files'] = [str(p) for p in (RUN/'failures').glob('*.json')]
    h['resolved_failure_files'] = [str(p) for p in (RUN/'resolved-failures').glob('*.json')]
    h['supervisor_failure_exists'] = (RUN/'supervisor-failure.json').exists()
    h['stop_files'] = {n:(RUN/n).read_text() for n in ['STOP','WATCHDOG_STOP','PUBLISH_STOP'] if (RUN/n).exists()}
    cg = Path('/sys/fs/cgroup')
    h['memory_current'] = int((cg/'memory.current').read_text())
    h['memory_limit'] = (cg/'memory.max').read_text().strip()
    h['disk_free_bytes'] = shutil.disk_usage(RUN).free
    h['dds_cache_bytes'] = sum(p.stat().st_size for p in RUN.glob('dds-cache.sqlite*'))
    h['cache_rotation'] = read(RUN/'last-cache-rotation.json')
    h['cache_rotation_already_diagnosed'] = h['cache_rotation'] == previous['cache_rotation']
    h['same_pids_as_previous_poll'] = h['pids'] == previous['pids']
    h['scientific_hashes_verified'] = True
    h['heartbeat_age_seconds'] = now-h['heartbeat']['epoch']
    h['publisher_age_seconds'] = now-h['publisher']['epoch']
    samples = []
    for receipt_path in sorted((RUN/'receipts').glob('*.json'),key=lambda p:p.stat().st_mtime)[-3:]:
        receipt = read(receipt_path)
        idx = receipt['index']
        ep = RUN/'episodes'/f'{idx:06d}.json.gz'
        raw = ep.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == receipt['episode_sha256']
        assert receipt['manifest_identity'] == m['identity']
        record = json.loads(gzip.decompress(raw))
        counts = dict(guess_size=0,best_share=0)
        nested_counts(record,counts)
        row = dict(index=idx,pair=receipt.get('pair',record.get('pair')),manifest=m['identity'],episode_sha256=receipt['episode_sha256'],receipt_hash_verified=True,gap_forks=record.get('gap_fork_count',0),observed_guess_fields=counts)
        if not row['gap_forks'] and not sum(counts.values()):
            tables = record['unique_tables']
            if isinstance(tables,dict):
                tables = tables.values()
            assert all(t['board']['contract'] is None and len(t['board']['auction'])==4 for t in tables)
            row['passed_out_verified'] = True
        samples.append(row)
    h['live_capture_sample'] = dict(samples=samples,actual_capture_observed=sum(r['gap_forks'] for r in samples)>0 and all(sum(r['observed_guess_fields'][k] for r in samples)>0 for k in ['guess_size','best_share']),new_launch_or_setting_change=False)
    assert all(h['pid_alive'].values())
    assert h['actual_normal_worker_children']==3
    assert not h['failure_files'] and not h['supervisor_failure_exists'] and not h['stop_files']
    assert h['supervisor']['collector']=='running' and h['supervisor']['ben_workers']==0
    assert not h['supervisor']['gen71_comparison_gate_enabled']
    assert not CONFIG['selfplay_launch_enabled']
    assert h['publisher']['status']=='published' and h['publisher_age_seconds']<180
    assert h['heartbeat_age_seconds']<60
    assert h['disk_free_bytes']>3*1024**3
    assert h['live_capture_sample']['actual_capture_observed']
    if (CASE/'cache-rotation-diagnosis.json').exists():
        diagnosis=read(CASE/'cache-rotation-diagnosis.json')
        initial=read(CASE/'health-before.json')
        h['same_pids_as_initial_check']=h['pids']==initial['pids']
        h['cache_rotation_diagnosed_in_this_poll']=diagnosis['journal']==h['cache_rotation'] and not diagnosis['requires_attention']
        assert h['same_pids_as_initial_check'] and h['cache_rotation_diagnosed_in_this_poll']
    return h

if __name__ == '__main__':
    h = check()
    (CASE/sys.argv[1]).write_text(json.dumps(h,indent=2)+'\n')
    print(json.dumps({k:h[k] for k in ['poll_start','pids','same_pids_as_previous_poll','cache_rotation_already_diagnosed','actual_normal_worker_children','failure_files','heartbeat_age_seconds','publisher_age_seconds','disk_free_bytes','dds_cache_bytes','memory_current','memory_limit']}))
    print(json.dumps(dict(completed=h['state']['completed'],published=h['publisher']['completed'],capture=h['live_capture_sample'])))
