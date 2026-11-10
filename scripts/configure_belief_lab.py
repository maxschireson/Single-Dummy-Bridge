"""Create an immutable, ordered experiment queue; all controls share validation."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.selfplay import atomic_json
from bridge_harness.belief_capacity import sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();root=a.run.resolve()
    if (root/'plan.json').exists():return
    data=root/'data';old=Path('/workspace/scratch/8fd3c92bf5b8/bridge-belief-v5')
    parent=old/'runs/belief-size-loss-v2-20261110/current_consequence/best.npz'
    auction=Path('/workspace/scratch/74fefc15be51/bridge-gen4-components/models/auction-belief.npz')
    v3=Path('/workspace/scratch/74fefc15be51/bridge-gen4-components/models/public-belief.npz')
    jobs=[];seed=2026111017
    def add(name,**changes):
        cfg=dict(mode='dense',parent=str(parent),data=str(data),epochs=6,seed=seed,batch_size=2048,lr=1e-4,threads=4,dropout=.15,cosine=True,consequence=True)
        cfg.update(changes);out=root/'fits'/name;out.mkdir(parents=True,exist_ok=True);atomic_json(out/'config.json',cfg)
        jobs.append(dict(name=name,config=str(out/'config.json')));return out
    # Raw-data-only increment is measured separately from recipe changes.
    add('dense_fixed',data=str(data/'fixed'));add('dense_added')
    add('dense_swap025',swap_weight=.25);add('dense_swap1',swap_weight=1.)
    add('dense_low_lr',lr=2e-5);add('dense_regularized',dropout=.30,weight_decay=.003)
    add('dense_count',count_loss=.1);add('dense_brier',brier=.3);add('dense_ordinary',consequence=False)
    add('dense_v3',parent=str(v3),lr=3e-4,epochs=8)
    # Early and late integration share ancestor, row ordering and batch size.
    warm=add('auction_warm',parent=str(auction),epochs=3,lr=3e-4,batch_size=256)
    add('dense_auction0',parent=str(auction),epochs=8,lr=3e-4,batch_size=256)
    add('attention_auction0',parent=str(auction),mode='attention',epochs=8,lr=3e-4,batch_size=256)
    add('dense_auction1',parent=str(warm/'epoch-1.npz'),epochs=7,lr=3e-4,batch_size=256)
    add('attention_auction1',parent=str(warm/'epoch-1.npz'),mode='attention',epochs=7,lr=3e-4,batch_size=256)
    add('dense_auction3',parent=str(warm/'epoch-3.npz'),epochs=5,lr=3e-4,batch_size=256)
    add('attention_auction3',parent=str(warm/'epoch-3.npz'),mode='attention',epochs=5,lr=3e-4,batch_size=256)
    add('dense_scratch',parent=None,lr=5e-4,epochs=10,batch_size=256)
    add('attention_scratch',parent=None,mode='attention',lr=5e-4,epochs=10,batch_size=256)
    add('dense_wide_scratch',parent=None,widths=[512,256],lr=5e-4,epochs=10,batch_size=256)
    add('dense_late_matched',batch_size=256,epochs=6,lr=3e-5)
    add('attention_late',mode='attention',batch_size=256,epochs=6,lr=3e-5)
    add('attention_frozen',mode='attention',freeze_base=True,batch_size=256,epochs=6,lr=1e-4)
    atomic_json(root/'plan.json',dict(schema='belief-lab-24h-v1',created=time.time(),deadline_utc='2026-11-11T04:30:00+00:00',
        baseline=str(parent),baseline_sha256=sha(parent),data_sha256=sha(data/'dataset.json'),jobs=jobs,
        screen_budget_hours=8,fit_budget_hours=14,confirmation_budget_hours=8,replication='Two additional seeds for dense_added and two best noncontrol recipes, selected using development only.',
        primary='Improvement over expanded-data dense control; unchanged v5 is secondary comparator.',
        selection='Frozen composite validation NLL; family-clustered paired differences; seed dispersion reported separately.',
        test_policy='Lock finalist before reserved prediction and 2000 fresh paired play boards per comparator. No tuning or replacing after confirmation.',
        promoted=False))

if __name__=='__main__':main()
