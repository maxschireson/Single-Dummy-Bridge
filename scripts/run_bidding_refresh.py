"""Train/evaluate fixed bidding mixes without DDS solves or live promotion."""
import argparse
import fcntl
import json
from pathlib import Path
import sys
import time
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge_harness.bidding_refresh import auction_pairs, common_support, clustered_summary, sha
from bridge_harness.bidding_loop import atomic_json
from bridge_harness.bidding_ppo import Policy, PPO


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--data', required=True, type=Path)
    p.add_argument('--parent', required=True, type=Path)
    p.add_argument('--anchor', required=True, type=Path)
    p.add_argument('--config', default='configs/bidding_clean_mixes.json', type=Path)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--phase', choices=['train', 'dev', 'test'], required=True)
    p.add_argument('--variant')
    p.add_argument('--play-root', required=True, type=Path)
    p.add_argument('--play-bot', default='3')
    p.add_argument('--dds-library', required=True, type=Path)
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    lock = (a.out/'writer.lock').open('a+')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    cfg = json.loads(a.config.read_text())
    play_spec = json.loads((a.play_root/'manifest.json').read_text())['bots'][a.play_bot]
    import tensorflow as tf
    tf.config.threading.set_intra_op_parallelism_threads(cfg['tf_threads'])
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.keras.utils.set_random_seed(cfg['seed'])
    identity = dict(schema='clean-bidding-mix-experiment-v1', config=cfg,
        dataset_sha256=sha(a.data), parent_sha256=sha(a.parent), anchor_sha256=sha(a.anchor),
        source_sha256={f: sha(Path(__file__).resolve().parents[1]/f) for f in
          ['bridge_harness/bidding_refresh.py','bridge_harness/bidding_ppo.py',
           'bridge_harness/bidding_play_cache.py','scripts/run_bidding_refresh.py']},
        tensorflow=tf.__version__, created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        parent=str(a.parent.resolve()), anchor=str(a.anchor.resolve()), data=str(a.data.resolve()),
        play_root=str(a.play_root.resolve()), play_spec=play_spec, dds_library_sha256=sha(a.dds_library),
        limitation='Historical and new play reuse assumes unchanged trick outcomes across auctions/levels for same strain/declarer',
        retention='KL to frozen original BEN on collected observations; not replay of original BEN corpus',
        promotion='No automatic promotion; test accessed only for preselected variant')
    manifest_path = a.out/'manifest.json'
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text())
        identity['created_utc'] = old['created_utc']
        if old != identity:
            raise ValueError('Frozen run provenance changed')
    else:
        atomic_json(manifest_path, identity)
    data = json.loads(a.data.read_text())
    parent, anchor = Policy.load(a.parent), Policy.load(a.anchor)
    variants = [v for v in cfg['variants'] if a.variant is None or v['name'] == a.variant]
    if not variants:
        raise ValueError('Unknown variant')

    def event(**row):
        row.update(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
        atomic_json(a.out/'status.json', row)
        print(json.dumps(row), flush=True)

    from bridge_harness.bidding_play_cache import MissingPlayCache
    cache = MissingPlayCache(a.out/'play-cache',a.play_root,play_spec,dds_library=a.dds_library,event=event)

    if a.phase == 'train':
        pools = {s: [r for r in data if r['source'] == s and r['split'] == 'train'] for s in ['play','dds']}
        for variant in variants:
            dest = a.out/variant['name']
            dest.mkdir(exist_ok=True)
            if (dest/'complete.json').exists():
                continue
            candidate = Policy.load(a.parent, critic=True)
            trainer = PPO(candidate, anchor, learning_rate=cfg['learning_rate'], epsilon=cfg['exploration'],
                          anchor_weight=variant['anchor_weight'])
            state = json.loads((dest/'state.json').read_text()) if (dest/'state.json').exists() else dict(offset=0)
            if state.get('checkpoint'):
                trainer.restore(state['checkpoint'])
            for offset in range(state['offset'], cfg['pairs_per_candidate'], cfg['batch_pairs']):
                start = time.monotonic()
                rng = np.random.default_rng(np.random.SeedSequence([cfg['seed'], offset]))
                n = min(cfg['batch_pairs'], cfg['pairs_per_candidate']-offset)
                nplay = int(round(n*variant['play_fraction']))
                batch = [pools['play'][i] for i in rng.choice(len(pools['play']), nplay, replace=False)]
                batch += [pools['dds'][i] for i in rng.choice(len(pools['dds']), n-nplay, replace=False)]
                rng.shuffle(batch)
                rows, decisions = auction_pairs(batch, candidate, parent, rng, explore=True,
                    epsilon=cfg['exploration'],missing_score=cache.score)
                metrics = trainer.train(decisions, rng, cfg['ppo_epochs'], cfg['minibatch']) if decisions else {}
                coverage = {s: dict(attempted=sum(r['source']==s for r in batch),
                            scored=sum(b['source']==s and r['imps'] is not None for b,r in zip(batch,rows))) for s in pools}
                atomic_json(dest/f'batch-{offset:05d}.json', dict(offset=offset, rows=rows, coverage=coverage,
                    metrics=metrics, seconds=time.monotonic()-start))
                state = dict(offset=offset+n, checkpoint=trainer.save(dest/'optimizer/ckpt'))
                atomic_json(dest/'state.json', state)
                event(phase='training', variant=variant['name'], completed_pairs=offset+n,
                      target_pairs=cfg['pairs_per_candidate'], coverage=coverage, seconds=time.monotonic()-start,
                      new_play_games=cache.plays,play_cache_hits=cache.hits)
            # Export the actor only, preserving BEN's native inference interface.
            actor = tf.keras.Model(candidate.model.inputs, candidate.model.outputs[0])
            actor.save(dest/'bidder.keras')
            atomic_json(dest/'complete.json', dict(variant=variant, pairs=cfg['pairs_per_candidate'],
                                                  sha256=sha(dest/'bidder.keras')))
        event(phase='training_complete', variants=[v['name'] for v in variants])
        cache.close()
        return

    if a.phase == 'test':
        selection = json.loads((a.out/'selection.json').read_text())
        if a.variant != selection['variant']:
            raise ValueError('Final test requires the frozen development selection')
    sources = ['play', 'dds'] if a.phase == 'dev' else ['play']
    summaries = {}
    for source in sources:
        evaluation = [r for r in data if r['source'] == source and r['split'] == a.phase]
        all_rows = {}
        for name in ['parent']+[v['name'] for v in variants]:
            candidate = parent if name == 'parent' else Policy.load(a.out/name/'bidder.keras')
            dest = a.out/f'{a.phase}-{source}-{name}.json'
            if dest.exists():
                rows = json.loads(dest.read_text())
            else:
                rows = []
                for offset in range(0, len(evaluation), cfg['batch_pairs']):
                    chunk, _ = auction_pairs(evaluation[offset:offset+cfg['batch_pairs']], candidate, parent,
                                             np.random.default_rng(cfg['seed']),missing_score=cache.score)
                    rows.extend(chunk)
                    event(phase='evaluation', split=a.phase, source=source, variant=name,
                          completed=len(rows), total=len(evaluation))
                atomic_json(dest, rows)
            all_rows[name] = rows
        common = common_support(all_rows)
        summaries[source] = dict(total_families=len({r['family'] for r in evaluation}),
            common_supported_families=len(common),
            variants={name: dict(common=clustered_summary(rows, set(common)),
                                  own_support=clustered_summary(rows)) for name, rows in all_rows.items()},
            support_note='Missing contracts played with frozen clean Gen3; every evaluated deal must be scored')
        if len(common) != summaries[source]['total_families']:
            raise ValueError('Incomplete evaluation after on-demand play')
    atomic_json(a.out/f'{a.phase}-summary.json', summaries)
    event(phase=a.phase+'_complete', summaries=summaries)
    cache.close()


if __name__ == '__main__':
    main()
