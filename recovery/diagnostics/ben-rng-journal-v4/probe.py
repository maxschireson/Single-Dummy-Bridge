"""Real archived V3.1 fixtures + explicitly synthetic 8128-entry storage test."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',TF_CPP_MIN_LOG_LEVEL='3')
import json,sys,time,shutil,subprocess,threading,traceback
from pathlib import Path
import journal as j
WORK=Path('/workspace/scratch/171a0eb26892/journal-v4-tests')

def fixtures():
    sys.path.insert(0,str(j.HERE.parent/'ben-rng-live-v31'))
    import adapter
    return adapter.accepted(j.HERE.parent/'ben-rng-live-v31/restored')[0]

def append(w,row):
    rec,raw,rng,_=row
    return w.append(rec['index'],raw,rng if 'ben' in rec['pair'] else None,j.sha(w.rng))

def reject(fn):
    try:fn()
    except (ValueError,FileNotFoundError,BlockingIOError):return
    raise AssertionError('expected rejection')

def race_snapshot(root,dest,writer,remaining):
    original=j.read;captured=threading.Event();release=threading.Event();result={}
    def paused_read(path,*args,**kwargs):
        value=original(path,*args,**kwargs)
        if Path(path)==root and threading.current_thread().name=='snapshot':
            result['captured']=json.loads(value[2])['count'];captured.set();release.wait(30)
        return value
    j.read=paused_read
    def run():
        try:result['copied']=j.snapshot(root,dest)
        except BaseException:result['error']=traceback.format_exc();captured.set()
    t=threading.Thread(target=run,name='snapshot');t.start()
    assert captured.wait(30),result
    try:
        for i,item in enumerate(remaining):
            writer(item)
            if i==0:release.set()
    finally:
        release.set();t.join(120);j.read=original
    assert not t.is_alive() and 'error' not in result,result
    assert result['copied']==result['captured']
    result['final']=len(j.read(root)[0])
    return result

def main():
    WORK.mkdir(exist_ok=False);rows=fixtures();assert len(rows)==8
    root=WORK/'real';j.initialize(root)
    with j.Writer(root) as w:
        for row in rows[:4]:append(w,row)
        reject(lambda:w.append(rows[4][0]['index'],rows[4][1],expected_rng='bad'))
        realrace=race_snapshot(root,WORK/'real-snapshot',lambda row:append(w,row),rows[4:])
        reject(lambda:j.Writer(root))
        reject(lambda:append(w,rows[0]))
    assert realrace==dict(captured=4,copied=4,final=8),realrace
    subprocess.run([sys.executable,__file__,'continue',str(WORK/'real-snapshot')],check=True)
    assert j.read(root)[1]==j.read(WORK/'real-snapshot')[1]==rows[-1][2]
    for name in ('real','real-snapshot'):
        j.materialize(WORK/name,WORK/(name+'-view'))
        sys.path.insert(0,str(j.ROOT))
        from ops.export_gen5 import export
        export(WORK/(name+'-view'),WORK/(name+'-export'))
    a=json.loads((WORK/'real-export/arena/data.json').read_bytes())
    b=json.loads((WORK/'real-snapshot-export/arena/data.json').read_bytes())
    keys=('completed','views','own_views','difference_views','allocation','manifest_identity')
    assert a['completed']==8 and all(a[k]==b[k] for k in keys)
    # Tampering fails closed. Test actual load, never an episode-directory scan.
    corrupt=WORK/'corrupt';j.snapshot(root,corrupt)
    head=json.loads((corrupt/'CURRENT').read_bytes());rngpath=j.object_path(corrupt,head['rng'])
    saved=rngpath.read_bytes();rngpath.write_bytes(b'corrupt');reject(lambda:j.read(corrupt));rngpath.unlink();reject(lambda:j.read(corrupt));rngpath.write_bytes(saved)
    protocol=corrupt/'PROTOCOL.json';saved=protocol.read_bytes();spec=json.loads(saved);spec['runtime'][str(j.HERE/'journal.py')]='0'*64;protocol.write_bytes(j.encode(spec));reject(lambda:j.read(corrupt));protocol.write_bytes(saved)
    # A valid but unreferenced episode object must not become accepted.
    j.put(corrupt,b'orphan episode');assert len(j.read(corrupt)[0])==8
    crashes=[]
    for kind,n in (('normal',0),('BEN',2)):
        for cut in ('episode','receipt','rng','node','objects_fsync','next_fsync','pointer_replace','commit_fsync'):
            path=WORK/('crash-'+kind+'-'+cut);j.initialize(path)
            p=subprocess.run([sys.executable,__file__,'crash',str(path),str(n)],env={**os.environ,'RNG_DIAGNOSTIC_CUT':cut},capture_output=True)
            assert p.returncode==-9,(cut,p.returncode,p.stderr.decode())
            got,rng,_=j.read(path);assert len(got) in (0,1)
            if got:assert got[0][0]['index']==rows[n][0]['index'] and rng==rows[n][2]
            # Replay the same staged fixture only if unaccepted; then append a new normal.
            with j.Writer(path) as w:
                if not got:append(w,rows[n])
                reject(lambda:append(w,rows[n]))
                append(w,rows[1])
            assert len(j.read(path)[0])==2
            crashes.append(dict(kind=kind,cut=cut,exit=p.returncode,recovered=len(got),continued=2))
    scale=WORK/'scale';j.initialize(scale,'synthetic-scaling')
    start=time.monotonic()
    with j.Writer(scale) as w:
        for i in range(2015):w.append_synthetic(i)
        scalerace=race_snapshot(scale,WORK/'scale-snapshot',w.append_synthetic,range(2015,8128))
    elapsed=time.monotonic()-start
    start=time.monotonic();recovered,rng,headraw=j.read(scale);recovery=time.monotonic()-start
    assert len(recovered)==8128 and scalerace==dict(captured=2015,copied=2015,final=8128),scalerace
    with j.Writer(scale) as w:
        reject(lambda:w.append_synthetic(0));w.append_synthetic(8128)
    reject(lambda:j.materialize(scale,WORK/'synthetic-export'))
    sizes=[p.stat().st_size for p in (scale/'objects').iterdir()]
    result=dict(status='passed',protocol=j.verify_spec(root)[1],production_commits=0,newly_played=0,
        fixture_records=8,real_snapshot=realrace,actual_export_equal=True,final_rng_exact=True,
        crash_tests=crashes,corrupt_missing_rng_rejected=True,runtime_mismatch_rejected=True,
        orphan_excluded=True,duplicate_and_second_writer_rejected=True,
        scaling=dict(kind='synthetic small records; not 8128 full game records',entries=8128,
                     continuation_entries=8129,concurrent_snapshot=scalerace,
                     append_and_snapshot_seconds=elapsed,recovery_seconds=recovery,
                     current_bytes=len(headraw),object_bytes=sum(sizes),objects=len(sizes)),
        limitations=['No live futures in V4','No in-flight collector death','No power-loss test',
                     'No production integration/adoption','Full recovery validates whole chain; snapshot copies all accepted objects',
                     'Existing V3.1 audit-volume mismatch is unchanged'])
    (j.HERE/'result.json').write_bytes(json.dumps(result,indent=2).encode());print(json.dumps(result),flush=True)
    # Preserve only small real fixture journals and exports; synthetic corpus is reproducible scratch.
    for name in ('real','real-snapshot','real-export','real-snapshot-export'):
        shutil.copytree(WORK/name,j.HERE/name)

if __name__=='__main__':
    if len(sys.argv)==1:main()
    elif sys.argv[1]=='continue':
        with j.Writer(Path(sys.argv[2])) as w:
            for row in fixtures()[4:]:append(w,row)
    elif sys.argv[1]=='crash':
        with j.Writer(Path(sys.argv[2])) as w:append(w,fixtures()[int(sys.argv[3])])
