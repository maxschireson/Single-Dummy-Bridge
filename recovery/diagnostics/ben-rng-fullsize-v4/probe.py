"""Storage-only scale diagnostic. NEVER eligible or playable records.

Each unique opaque payload is an original compressed episode plus a synthetic
gzip member. This preserves the full archived byte volume without pretending
that 8,128 new games were played. Calls the journal's private storage primitive,
not its real-record validator; synthetic mode prohibits actual export.
"""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
import gc, gzip, hashlib, json, random, resource, shutil, subprocess, sys
import threading, time, traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parents[1]
sys.path.insert(0, str(HERE.parent/'ben-rng-journal-v4'))
import journal as j
WORK = Path('/tmp/bridge-v4-fullsize-20261112-0940')
TEMPLATES = sorted((RUN/'episodes').glob('*.json.gz'))

def tupled(v):
    return tuple(map(tupled, v)) if isinstance(v, list) else v

def append(w, index):
    source = TEMPLATES[index % len(TEMPLATES)].read_bytes()
    raw = source + gzip.compress(j.encode({'synthetic_storage_index': index}), mtime=0)
    receipt = j.encode(dict(index=index, episode_sha256=j.sha(raw), eligible=False,
                           storage_test=True, archived_prefix_sha256=j.sha(source)))
    kind = 'BEN' if index % 13 == 0 else 'normal'
    post = None
    if kind == 'BEN':
        rng = random.Random(); rng.setstate(tupled(json.loads(w.rng)))
        rng.random()  # Synthetic transition, never a BEN inference claim.
        post = j.encode(rng.getstate())
    w._append(index, raw, receipt, kind, post, j.sha(w.rng))

def inventory(root):
    digest=hashlib.sha256(); count=0; size=0
    for p in sorted((root/'objects').iterdir()):
        b=p.read_bytes(); assert j.sha(b)==p.name
        digest.update((p.name+' '+str(len(b))+'\n').encode())
        count+=1; size+=len(b)
    return dict(objects=count, bytes=size, sorted_inventory_sha256=digest.hexdigest())

def measure_read(root, count):
    t=time.monotonic(); rows,rng,head=j.read(root)
    assert len(rows)==count
    stats=dict(records=len(rows), seconds=time.monotonic()-t,
               payload_bytes=sum(len(row[1]) for row in rows),
               head_sha256=j.sha(head), rng_sha256=j.sha(rng),
               current_bytes=len(head), peak_rss_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    del rows; gc.collect()
    return stats

def continuation():
    root=WORK/'snapshot'
    assert json.loads((root/'CURRENT').read_bytes())['count']==2015
    t=time.monotonic()
    with j.Writer(root) as w:
        for i in range(2015,8128): append(w,i)
    result=measure_read(root,8128)
    result['continuation_seconds']=time.monotonic()-t
    assert (root/'CURRENT').read_bytes()==(WORK/'live/CURRENT').read_bytes()
    assert inventory(root)==inventory(WORK/'live')
    with j.Writer(root) as w: append(w,8128)
    result['after_next']=measure_read(root,8129)
    (HERE/'continuation.json').write_text(json.dumps(result,indent=2))

def main():
    WORK.mkdir(exist_ok=False)
    assert len(TEMPLATES)==2015
    fixture=[dict(path=p.name,sha256=j.sha(p.read_bytes()),size=p.stat().st_size) for p in TEMPLATES]
    (HERE/'templates.json').write_text(json.dumps(fixture,indent=2))
    root=WORK/'live'; j.initialize(root, 'synthetic-scaling')
    start=time.monotonic(); captured=threading.Event(); release=threading.Event(); race={}
    original_read=j.read
    def paused_read(path,*args,**kwargs):
        value=original_read(path,*args,**kwargs)
        if Path(path)==root and threading.current_thread().name=='snapshot':
            race['captured']=json.loads(value[2])['count']; captured.set()
            assert release.wait(60)
        return value
    def snap():
        try: race['copied']=j.snapshot(root,WORK/'snapshot')
        except BaseException: race['error']=traceback.format_exc(); captured.set()
    with j.Writer(root) as w:
        for i in range(2015): append(w,i)
        j.read=paused_read
        t=threading.Thread(target=snap,name='snapshot'); t.start()
        assert captured.wait(60),race
        try:
            for i in range(2015,8128):
                append(w,i)
                if i==2015: release.set()
                if i%1000==0: print(json.dumps({'appended':i+1}),flush=True)
        finally:
            release.set(); t.join(60); j.read=original_read
        assert not t.is_alive() and 'error' not in race,race
    assert race=={'captured':2015,'copied':2015},race
    write_seconds=time.monotonic()-start
    live=measure_read(root,8128); stored=inventory(root)
    assert measure_read(WORK/'snapshot',2015)['records']==2015
    try: j.materialize(root,WORK/'forbidden-export')
    except ValueError as e: assert str(e)=='synthetic export forbidden'
    else: raise AssertionError('synthetic export accepted')
    gc.collect()
    subprocess.run([sys.executable,__file__,'continue'],check=True)
    result=dict(schema='diagnostic-v4-fullsize-storage-v1',eligible=False,
        journal_sha256=j.sha((j.HERE/'journal.py').read_bytes()),
        protocol_sha256=j.sha((root/'PROTOCOL.json').read_bytes()),
        template_count=len(fixture), templates_sha256=j.sha((HERE/'templates.json').read_bytes()),
        template_bytes=sum(x['size'] for x in fixture),write_seconds=write_seconds,
        live=live,inventory=stored,snapshot=race,
        continuation=json.loads((HERE/'continuation.json').read_text()),
        synthetic_export_rejected=True,production_commits=0,newly_played_games=0,
        limits='Opaque full-size synthetic payloads using archived episode bytes; private storage primitive only. No real-record validator/export, new gameplay, scanner integration, crash/powerloss or cleanup test. Synthetic RNG advances are not BEN inference. Existing 1934 equivalence mismatch remains unresolved.',
        payload_storage='Temporary reproducible payloads removed only after all checks; driver and template hashes retained.')
    (HERE/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
    shutil.rmtree(WORK)

if __name__=='__main__':
    if len(sys.argv)>1: continuation()
    else: main()
