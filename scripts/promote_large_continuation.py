#!/usr/bin/env python3
"""Publish a completed belief continuation at a stopped collection boundary."""
import argparse
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arena',type=Path,required=True)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--stopped-collection',type=Path,required=True)
    a=p.parse_args()
    sys.path.insert(0,str(a.arena.resolve()))
    from bridge_harness.improvement import writer_lock
    from bridge_harness.loop_registry import freeze_bot,verify_bot,sha
    from bridge_harness.selfplay import atomic_json
    from ops.promote_belief_on_predictions import prediction_gate
    reg=a.arena/'runs/prediction-led-collection'
    result=json.loads((a.run/'large/result.json').read_text())
    config=json.loads((a.run/'large/config.json').read_text())
    if not result['complete'] or not result['promotion_eligible']:raise ValueError('No completed eligible candidate')
    if sha(a.run/'data/dataset.json')!=result['dataset_sha256']:raise ValueError('Dataset changed')
    if sha(result['selected_weights'])!=result['selected_sha256']:raise ValueError('Candidate changed')
    gate=prediction_gate(result['initial_validation'],result['selected_validation'])
    if not gate['promote']:raise ValueError('Prediction gate failed')
    # Never alter any live block. These locks only assert the old collection has drained.
    import fcntl
    held=[]
    for name in ('.writer.lock','.slice-supervisor.lock'):
        h=(a.stopped_collection/name).open('r');fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB);held.append(h)
    if not (a.stopped_collection/'STOP').exists():raise ValueError('Collection stop missing')
    stop=json.loads((a.stopped_collection/'collection-stopped.json').read_text())
    if not stop['stopped'] or stop['bad_records']:raise ValueError('Collection not finalized')
    with writer_lock(reg):
        current=json.loads((reg/'current.json').read_text())
        if sha(reg/'current.json')!=config['registry_sha256']:raise ValueError('Collector changed; revalidate against current parent')
        parent_path=Path(current['collector']);parent=verify_bot(parent_path)
        if parent['identity']!=result['collector_identity']:raise ValueError('Parent identity mismatch')
        spec=dict(parent['spec'])
        spec['artifacts']={k:str(parent_path.parent/v['file']) for k,v in spec['artifacts'].items()}
        spec['artifacts']['belief']=result['selected_weights']
        dest=freeze_bot(a.run,'large-8315',spec);bot=verify_bot(dest)
        event=dict(schema=1,status='promoted-for-next-collection-block',
            utc=datetime.now(timezone.utc).isoformat(),collector=str(dest.resolve()),collector_identity=bot['identity'],
            previous_collector=current['collector'],previous_collector_identity=current['collector_identity'],
            reference=current['reference'],reference_identity=current['reference_identity'],
            samples=current['samples'],validation=gate,dataset_sha256=result['dataset_sha256'],
            validation_result_sha256=sha(a.run/'large/result.json'),
            play_confirmation='future random-audit mixed pool; no IMP prerequisite',
            boundary='v2 stopped; old mixed collector retired; active frozen manifests unchanged',
            collection=current['collection'])
        atomic_json(a.run/'previous-collector.json',current)
        atomic_json(a.run/'promotion-event.json',event)
        atomic_json(reg/'current.json',event)
        print(json.dumps(event))

if __name__=='__main__':main()
