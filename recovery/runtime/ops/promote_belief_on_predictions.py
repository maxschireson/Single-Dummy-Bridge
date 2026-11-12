"""Prediction-based belief promotion, independent of noisy card-play results."""
import argparse
from datetime import datetime, timezone
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from bridge_harness.improvement import read, writer_lock
from bridge_harness.loop_registry import sha, verify_bot
from bridge_harness.selfplay import atomic_json


def prediction_gate(before, after):
    """Same observation domains/weights as the frozen model-selection recipe."""
    rows=[]
    for source,view,weight in [('play','all',.5),('bidding','complete_auction',.25),('ben','complete_auction',.25)]:
        a,b=before[source][view],after[source][view]
        if a['uncertain_card_labels']!=b['uncertain_card_labels'] or a['uncertain_card_labels']<=0:
            raise ValueError('Parent and candidate must be evaluated on identical validation labels')
        if not all(math.isfinite(x['nll']) and x['nll']>=0 and math.isfinite(x['accuracy']) and 0<=x['accuracy']<=1 for x in (a,b)):
            raise ValueError('Invalid prediction metrics')
        rows.append(dict(source=source,view=view,weight=weight,parent=a,candidate=b))
    ce_before=sum(r['weight']*r['parent']['nll'] for r in rows)
    ce_after=sum(r['weight']*r['candidate']['nll'] for r in rows)
    acc_before=sum(r['weight']*r['parent']['accuracy'] for r in rows)
    acc_after=sum(r['weight']*r['candidate']['accuracy'] for r in rows)
    return dict(promote=ce_after<ce_before and acc_after>acc_before,
        parent_cross_entropy=ce_before,candidate_cross_entropy=ce_after,
        parent_ownership_accuracy=acc_before,candidate_ownership_accuracy=acc_after,
        domains=rows,rule='Lower weighted validation cross entropy AND higher weighted ownership accuracy; no IMP significance requirement')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,default=Path('/workspace/scratch/9357bfc2ac0b/bridge-belief-sizes/runs/belief-sizes-v1'))
    p.add_argument('--pilot',type=Path,default=ROOT/'runs/large-belief-play-16-v1')
    p.add_argument('--registry',type=Path,default=ROOT/'runs/prediction-led-collection')
    a=p.parse_args();a.registry.mkdir(parents=True,exist_ok=True)
    with writer_lock(a.registry):
        result=read(a.study/'large/result.json');dataset=read(a.study/'data/dataset.json')
        manifest=read(a.pilot/'manifest.json')
        candidate=verify_bot(manifest['bots']['large']);parent=verify_bot(manifest['bots']['incumbent'])
        assert result['complete'] and not result['test_evaluated'] and dataset['validated']
        assert dataset['parent_sha256']==parent['spec']['artifacts']['belief']['sha256']
        assert result['selected_sha256']==candidate['spec']['artifacts']['belief']['sha256']
        assert sha(a.study/'data/dataset.json')==manifest['dataset_sha256']
        gate=prediction_gate(result['initial_validation'],result['selected_validation'])
        if not gate['promote']:raise ValueError('Candidate does not improve both prediction measures')
        decision=dict(schema=1,status='promoted-for-collection',
            collector=manifest['bots']['large'],collector_identity=candidate['identity'],
            reference=manifest['bots']['incumbent'],reference_identity=parent['identity'],
            validation=gate,validation_result_sha256=sha(a.study/'large/result.json'),
            dataset_sha256=manifest['dataset_sha256'],samples=16,
            play_confirmation='accumulate-from-mixed-pool; not a promotion prerequisite',
            collection=dict(mode='paired-partnership',directions=['candidate-NS','candidate-EW'],
                exploration=0,score_before_training=True,freeze_versions_within_block=True,
                retain_reference=True,save_exact_dds_solves=True),
            authorizing_instruction='Promote based on lower cross entropy and better ownership predictions; obtain confirmation from mixed pool play.')
        path=a.registry/'current.json'
        if path.exists():
            if read(path)!=decision:raise ValueError('Existing promotion differs; record a new generation explicitly')
        else:
            atomic_json(path,decision)
            atomic_json(a.registry/'promotion-event.json',dict(**decision,utc=datetime.now(timezone.utc).isoformat()))
        print(path)


if __name__=='__main__':main()
