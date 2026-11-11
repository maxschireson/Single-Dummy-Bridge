"""Export the exact reviewed PPO bidder's actor for frozen BEN net-only auctions."""
import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if (a.out/'promotion.json').exists():raise ValueError('Promotion already exported; verify and reuse it')
    review=read(a.review/'summary.json');spec=read(a.review/'spec.json');snap=a.review/'snapshot'
    if review['pairs']!=5000 or review['trained_pairs']!=40000 or review['snapshot_sha256']!=spec['snapshot_sha256']:
        raise ValueError('Expected the exact 40k / 5k frozen review')
    state=read(snap/'run/state.json');manifest=read(snap/'run/manifest.json');hashes=read(snap/'SHA256.json')
    if state['trained_pairs']!=40000 or state['step']!=314:raise ValueError('Unexpected training checkpoint')
    origin=snap/'dependencies'/Path(manifest['origin']).name
    prefix=snap/'run/checkpoints'/Path(state['checkpoint']).parent.name/Path(state['checkpoint']).name
    files=[origin,snap/'run/state.json',snap/'run/manifest.json',*prefix.parent.glob(prefix.name+'.*')]
    for file in files:
        expected=hashes.get(str(file.relative_to(snap)))
        if expected is None or sha(file)!=expected:raise ValueError(f'Frozen snapshot changed: {file}')
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(1);tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(manifest['config']['seed'])
    from bridge_harness.bidding_ppo import Policy,PPO
    from bridge_harness.bidding_env import BidObservation,encode,pack_inputs,legal_mask,masked_probabilities
    from bridge_harness.corpus import generate
    anchor=Policy.load(origin);candidate=Policy.load(origin,critic=True);cfg=manifest['config']
    trainer=PPO(candidate,anchor,learning_rate=cfg['learning_rate'],epsilon=cfg['exploration'],anchor_weight=cfg['anchor_weight'])
    trainer.restore(prefix)
    # Exclude the training-only critic. BEN deployment expects one actor output.
    actor=tf.keras.Model(candidate.model.inputs,candidate.model.outputs[0])
    dest=a.out/'bidder-40000.keras';actor.save(dest)
    deployed=Policy.load(dest)
    observations=[]
    for board in generate(64,202611094):
        for calls in ((),('PASS',),('1C','PASS'),('1N','PASS','3N')):
            seat=(board.dealer+len(calls))%4
            observations.append(BidObservation(board.hands[seat],seat,board.dealer,board.vulnerability,calls))
    x,lengths=pack_inputs([encode(o) for o in observations]);before,_=candidate.predict(x,lengths);after,_=deployed.predict(x,lengths)
    error=float(np.max(np.abs(before-after)))
    masks=np.stack([legal_mask(o.dealer,o.calls) for o in observations])
    changed=int(np.sum(masked_probabilities(before,masks).argmax(1)!=masked_probabilities(after,masks).argmax(1)))
    if error>1e-6 or changed:raise ValueError('Actor export changed predictions or legal greedy choices')
    atomic_json(a.out/'promotion.json',dict(schema='validated-bidder-promotion-v1',epoch=time.time(),
        authority='User: Push the new bidding network and restart.',trained_pairs=40000,ppo_updates=314,
        source_snapshot_sha256=review['snapshot_sha256'],source_checkpoint=str(prefix),
        source_file_sha256={str(f.relative_to(snap)):sha(f) for f in files},review=review,
        actor_file=dest.name,actor_sha256=sha(dest),actor_parameters=actor.count_params(),
        export_checks=dict(observations=len(observations),max_probability_error=error,changed_legal_greedy_choices=changed),
        deployment='Greedy neural-only bidding; no DDS/search/rescue. Actor exported without training critic.',
        interpretation='User-authorized adoption following positive descriptive held-out DDS results; no claim of real-cardplay bidding validation.'))
    print(json.dumps(dict(actor=str(dest),sha256=sha(dest),observations=len(observations),max_probability_error=error,changed_choices=changed)))


if __name__=='__main__':main()
