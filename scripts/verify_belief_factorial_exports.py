"""Check selected NumPy exports against saved TensorFlow/AdamW checkpoints."""
import argparse,json,math,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bridge_harness.belief_capacity import INPUTS,Weights,load,make_model,sha
from scripts.screen_attention_belief import save_json

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args()
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    experiment=json.loads((a.run/'experiment.json').read_text())
    dataset=json.loads((Path(experiment['data'])/'dataset.json').read_text())
    samples={}
    for entry in dataset['shards']:
        domain=entry['cohort']+'/'+entry['source']
        if entry['split']!='validation' or domain in samples:continue
        if sha(entry['file'])!=entry['sha256']:raise ValueError('Changed validation shard')
        data=load(entry['file']);samples[domain]={k:data[k][:128] for k in INPUTS}
    checks={}
    for cell,widths,_ in experiment['cells']:
        tf.keras.backend.clear_session()
        root=a.run/cell;result=json.loads((root/'result.json').read_text())
        config=json.loads((root/'config.json').read_text());state=json.loads((root/'state.json').read_text())
        model=make_model(tuple(widths))
        optimizer=tf.keras.optimizers.AdamW(config['learning_rate'],weight_decay=.0001,clipnorm=1.)
        optimizer.build(model.trainable_variables)
        checkpoint=tf.train.Checkpoint(model=model,optimizer=optimizer)
        checkpoint.restore(state['selected_checkpoint']).assert_existing_objects_matched()
        exported=Weights(root/'best.npz')
        if sha(root/'best.npz')!=result['selected_sha256']:raise ValueError('Changed export')
        for actual,saved in zip(model.get_weights(),exported.weights):
            np.testing.assert_array_equal(actual,saved)
        expected_steps=result['best_epoch']*sum(math.ceil(e['rows']/config['batch_size']) for e in dataset['shards'] if e['split']=='train')
        if int(optimizer.iterations.numpy())!=expected_steps:raise ValueError('Optimizer epoch mismatch')
        if not all(np.isfinite(v.numpy()).all() for v in optimizer.variables):raise ValueError('Nonfinite optimizer')
        errors={domain:float(np.max(np.abs(exported.predict(x)-model(x,training=False).numpy()))) for domain,x in samples.items()}
        if max(errors.values())>1e-5:raise ValueError('Export predictions differ')
        checks[cell]=dict(selected_epoch=result['best_epoch'],optimizer_steps=expected_steps,weights_array_equal=True,
            logit_max_abs_error=errors,selected_sha256=result['selected_sha256'])
    save_json(a.run/'export-verification.json',checks)
    print(json.dumps(checks,indent=2))

if __name__=='__main__':main()
