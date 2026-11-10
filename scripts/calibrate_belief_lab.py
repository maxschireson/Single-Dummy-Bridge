"""Development-only temperature and public-capacity projection screen."""
import argparse,json,os,sys,time
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_lab import Weights
from bridge_harness.selfplay import atomic_json
from bridge_harness.belief_capacity import sha
from scripts.residual_belief_common import evaluate

def main():
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    entries=[e for e in json.loads((a.data/'dataset.json').read_text())['shards'] if e['split']=='validation']
    rows=[]
    # Seat/card offsets cancel in WeightedSampler's exact conditional product.
    # Projection can improve marginal scoring but cannot improve that sampler;
    # never use projection's apparent gain to select a playing model.
    for projection in (False,):
        for temperature in (.7,.85,1.,1.15,1.3,1.6):
            name=f't{temperature:.2f}_p{int(projection)}';rp=a.out/(name+'.json');mp=a.out/(name+'-metrics.json')
            recipe=dict(model=str(a.model.resolve()),temperature=temperature,projection=projection)
            if rp.exists() and json.loads(rp.read_text())!=recipe:raise ValueError('Calibration changed')
            atomic_json(rp,recipe)
            if mp.exists():metrics=json.loads(mp.read_text())
            else:
                model=Weights(rp);start=time.time();metrics=evaluate(model.predict,entries,a.out,name,256)
                metrics['seconds']=time.time()-start;atomic_json(mp,metrics)
            rows.append(dict(recipe=str(rp.resolve()),metrics=metrics));print(json.dumps(dict(calibration=name,score=metrics['score'])),flush=True)
    best=min(rows,key=lambda r:r['metrics']['score'])
    atomic_json(a.out/'result.json',dict(selected=best,rows=rows,model_sha256=sha(a.model),data_sha256=sha(a.data/'dataset.json'),test_evaluated=False))

if __name__=='__main__':main()
