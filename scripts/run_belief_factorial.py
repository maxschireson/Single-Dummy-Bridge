"""Four sequential, resumable dense size/loss cells on one frozen dataset."""
import argparse,fcntl,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import sha
from scripts.screen_attention_belief import save_json

CELLS=[('current_ordinary',[256,128],'ordinary'),('large_ordinary',[512,256],'ordinary'),
       ('current_consequence',[256,128],'consequence'),('large_consequence',[512,256],'consequence')]

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--smoke-shards',type=int,default=0)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    lock=(a.out/'pipeline.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cfg=dict(schema='dense-belief-size-loss-2x2-v1',data=str(a.data.resolve()),dataset_sha256=sha(a.data/'dataset.json'),
        input_manifest_sha256=sha(a.data/'manifest.json'),parent_sha256=sha('models/belief-v4.npz'),
        code_sha256={n:sha(n) for n in ['scripts/train_belief_factorial.py','bridge_harness/belief_capacity.py']},
        cells=CELLS,epochs=3,threads=2,seed=2026111001,smoke_shards=a.smoke_shards,
        optimizer='Reset AdamW for all four cells; lr 0.0001, wd 0.0001, clip 1.',
        primary='Paired size and loss contrasts at fixed epoch 3; same frozen composite validation objective.',
        secondary='Per-cell best epoch including v4 epoch 0; paired ordinary and consequential-card metrics; descriptive SE after selection.',
        test_evaluated=False,promoted=False)
    cfg=json.loads(json.dumps(cfg));path=a.out/'experiment.json'
    if path.exists():
        if json.loads(path.read_text())!=cfg:raise ValueError('Experiment configuration changed')
    else:save_json(path,cfg)
    started=time.time();env={**os.environ,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1','TF_CPP_MIN_LOG_LEVEL':'3'}
    results={}
    for name,widths,loss in CELLS:
        out=a.out/name
        if not (out/'result.json').exists():
            save_json(a.out/'status.json',dict(stage='training',active_cell=name,completed=list(results),updated=time.time()))
            cmd=[sys.executable,'-u','scripts/train_belief_factorial.py','--data',str(a.data),'--out',str(out),
                 '--widths',*map(str,widths),'--loss',loss,'--threads','2','--epochs','3']
            if a.smoke_shards:cmd+=['--smoke-shards',str(a.smoke_shards)]
            with (a.out/'pipeline.log').open('a',buffering=1) as log:
                log.write(json.dumps(dict(cell=name,started=time.time()))+'\n')
                subprocess.run(cmd,env=env,stdout=log,stderr=log,check=True)
        result=json.loads((out/'result.json').read_text())
        if result['config_sha256']!=sha(out/'config.json'):raise ValueError('Cell config changed')
        results[name]=dict(parameters=result['parameters'],selected_epoch=result['best_epoch'],
            selected_score=result['selected']['score'],last_score=result['history'][-1]['metrics']['score'],
            result_sha256=sha(out/'result.json'))
        save_json(a.out/'status.json',dict(stage='training',completed=list(results),results=results,updated=time.time()))
        print(json.dumps(dict(cell=name,**results[name])),flush=True)
    save_json(a.out/'status.json',dict(stage='complete',completed=list(results),results=results,
        elapsed_this_invocation=time.time()-started,updated=time.time(),test_evaluated=False,promoted=False))

if __name__=='__main__':main()
