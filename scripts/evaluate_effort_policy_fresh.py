"""Secondary Gen5 development check, keeping every hash-zero test deal untouched."""
import argparse,gzip,hashlib,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.core import Board,Game,card
from bridge_harness.bidding_env import deal_key
from bridge_harness.auction_policy import encode_decision,AuctionSelectorWeights
from bridge_harness.belief_capacity import sha
from bridge_harness.selfplay import atomic_json
from scripts.screen_attention_belief import split
from scripts.report_effort_pilot import contrast

def prepare(root):
    path=root/'fresh-policy-development.npz'
    if path.exists():return path
    plan=json.loads((root/'plan.json').read_text());excluded=set()
    # Original families are all ineligible for this additional development pool.
    base=Path(plan['belief_base']);ds=json.loads((base/'dataset.json').read_text());dm=json.loads((base/'manifest.json').read_text());excluded.update(dm['reserved_families'])
    for e in ds['shards']:
        with np.load(e['file']) as z:excluded.update(map(str,z['split_group']))
    p=json.loads(Path('/workspace/scratch/8fd3c92bf5b8/timing-v4/restored-v4/partition.json').read_text());excluded.update(p['train_families']);excluded.update(p['validation_families'])
    excluded.update(e['family'] for e in json.loads((Path(plan['policy_base'])/'families.json').read_text()))
    rows=[];sources=[]
    for label,folder,actor in [('high','effort-high','5'),('low','effort-feed','5-32')]:
        source=Path('/workspace/scratch/e9691f0e7615')/folder/'recovery'
        for f in sorted((source/'episodes').glob('*.json.gz')):
            r=json.loads(gzip.decompress(f.read_bytes()));family=r['family']
            if r['candidate']!=actor or r['opponent'] not in ('4b','3','2','1') or family in excluded or split(family)!='validation':continue
            assert r['manifest_identity']==plan['provenance'][label]['manifest']['identity']
            family_rows=[]
            for key in set(r['regimes']['common']['tables']):
                room=r['unique_tables'][key];board=Board.from_dict(room['board']);assert deal_key(board.hands,True)==family
                if board.contract is None:continue
                t=next(t for t in room['tables'] if t.get('node')=='root');g=Game(board)
                eligible=[i for i,z in enumerate(t['actions']) if z.get('estimates') and sum(v>0 for v in z.get('proposal_probabilities',z.get('behavior_probabilities',{})).values())>=2]
                take=set(sorted(eligible,key=lambda i:hashlib.sha256((family+'|'+str(room['seed'])+'|'+str(i)).encode()).hexdigest())[:16])
                for i,z in enumerate(t['actions']):
                    o=g.observation()
                    if i in take:
                        x,cards=encode_decision(o,z,synthetic=board.auction_source in (None,'synthetic'));ix=np.flatnonzero((cards[0]==card(z['card']))&(x['mask'][0]>0));assert len(ix)==1
                        decl=o.actor%2==o.contract.declarer%2;final=t['declarer_tricks'] if decl else 13-t['declarer_tricks'];already=o.declarer_tricks if decl else len(o.history)//4-o.declarer_tricks
                        row={k:v[0] for k,v in x.items()};row.update(chosen=np.int8(ix[0]),y=np.float32(final-already),group=np.array(family),cohort=np.array(label));family_rows.append(row)
                    assert z['seat']=='NESW'[o.actor];g.play(card(z['card']))
                assert g.done and g.ns_score()==t['ns_score']
            rows.extend(family_rows);sources.append(dict(file=str(f),sha256=sha(f),family=family,cohort=label,rows=len(family_rows)))
    np.savez_compressed(path,**{k:np.stack([r[k] for r in rows]) for k in rows[0]})
    atomic_json(root/'fresh-policy-development.json',dict(created=time.time(),sources=sources,sha256=sha(path),evaluation_only=True,rule='Secondary descriptive Gen5 outcome evaluation; hash-five only, never train. Cohorts separately reported; no model selection from this pool in the pilot.'))
    return path

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--prepare-only',action='store_true');a=p.parse_args();root=a.run.resolve();path=prepare(root)
    if a.prepare_only:return
    with np.load(path) as z:d={k:z[k] for k in z.files}
    rows=[]
    for epoch in (0,1,2):
        scores={}
        for arm in ('none','high','low','quantity'):
            model=root/'fits'/('policy_'+arm)/f'epoch-{epoch}.npz';dest=model.with_name(f'fresh-{epoch}.json')
            if not model.exists():continue
            if dest.exists():scores[arm]=json.loads(dest.read_text());continue
            w=AuctionSelectorWeights(model);groups={}
            for lo in range(0,len(d['y']),128):
                b={k:v[lo:lo+128] for k,v in d.items()};pred=w.predict(b);error=(pred[np.arange(len(pred)),b['chosen']]-b['y'])**2
                for g,cohort,v in zip(b['group'],b['cohort'],error):
                    acc=groups.setdefault(str(cohort)+'|'+str(g),[0.,0]);acc[0]+=float(v);acc[1]+=1
            atomic_json(dest,groups);scores[arm]=groups
        if len(scores)<4:continue
        for cohort in ('high','low'):
            sub={k:{g:v for g,v in gs.items() if g.startswith(cohort+'|')} for k,gs in scores.items()}
            for left,right in [('high','low'),('high','quantity'),('high','none'),('quantity','none')]:rows.append(dict(epoch=epoch,cohort=cohort,left=left,right=right,**contrast(sub[left],sub[right])))
    atomic_json(root/'fresh-policy-comparison.json',dict(rows=rows,interpretation='Secondary descriptive outcome MSE on new Gen5 development families, conditioned on recorded continuation effort; not an independent playing-strength test.'))
    print(json.dumps(dict(rows=rows)),flush=True)

if __name__=='__main__':main()
