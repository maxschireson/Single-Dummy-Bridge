#!/usr/bin/env python3
"""Export completed direct-arena records as training-only compressed tensors.

Uses the same encoding, deterministic sampling, labels and weights as
scripts/prepare_mixed_training.py, without requiring the campaign to finish.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from bridge_harness.auction_policy import encode_decision
from bridge_harness.belief_capacity import SCHEMA, encode_play, load as load_belief
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board, Game, card
from bridge_harness.improvement import read
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import validate_pair, verify_generation
from bridge_harness.training import digest


def training_rows(record):
    board = Board.from_dict(record['board'])
    family = record['family']
    episodes = list(record['unique_tables'].values()) if 'unique_tables' in record else [record['focal'], record['control'], *record.get('extra_episodes', [])]
    policy = []
    events = [(episode, event) for episode in episodes
              for event in episode['audits'] if not event['identical_action']]
    for episode, event in events:
        table = episode['tables'][event['candidate_table']]
        ply = event['ply']
        game = Game(Board.from_dict(episode['board']))
        for action in table['actions'][:ply]:
            game.play(card(action['card']))
        x, cards = encode_decision(game.observation(), table['actions'][ply])
        valid = x['mask'][0] > 0
        chosen = int(np.flatnonzero(valid & (cards[0] == card(event['candidate_card'])))[0])
        reference = int(np.flatnonzero(valid & (cards[0] == card(event['reference_card'])))[0])
        row = {k: v[0] for k, v in x.items()}
        row.update(chosen=np.int32(chosen), reference=np.int32(reference),
                   y=np.float32(event['gain_imps']), weight=np.float32(1/max(1, len(events))),
                   group=family)
        policy.append(row)
    seen = set()
    belief = []
    for episode in episodes:
        for table in episode['tables']:
            trajectory = digest([family, [a['card'] for a in table['actions']]])
            rng = np.random.default_rng(int(trajectory[:16], 16))
            selected = set(np.concatenate([rng.choice(np.arange(lo, lo+13), 4, replace=False)
                                           for lo in (0, 13, 26, 39)]))
            game = Game(Board.from_dict(episode['board']))
            for action in table['actions']:
                key = tuple(c for _, c in game.history)
                if len(game.history) in selected and key not in seen:
                    seen.add(key)
                    o = game.observation()
                    x, support = encode_play(o)
                    mask = support.sum(-1) > 1
                    if mask.any():
                        target = np.zeros(52, np.int8)
                        for seat, hand in enumerate(game.hands):
                            target[list(hand)] = (seat-o.controller) % 4
                        if np.any(mask & ~support[np.arange(52), target]):
                            raise ValueError('True owner excluded')
                        belief.append(dict(**x, owner_target=target, owner_loss_mask=mask,
                                           support=support, kind=np.int8(2), split_group=family))
                game.play(card(action['card']))
    if len(belief) > 128:
        rng = np.random.default_rng(int(family[:16], 16))
        belief = [belief[i] for i in sorted(rng.choice(len(belief), 128, replace=False))]
    return dict(policy=policy, belief=belief)


def export(run, out, exclude_families=(), limit=None):
    if out.exists():
        raise ValueError('Refusing to overwrite an existing frozen export')
    manifest = read(run/'manifest.json')
    if manifest.get('protocol') not in ('direct-pairs-v1', 'v4-bidder-crossover-v1') and manifest.get('schema') != 'gen4-component-primary-v1':
        raise ValueError('Direct campaign required; legacy remains separate')
    verify_generation(run, manifest)
    # Freeze the receipt list once. New commits continue independently.
    paths = sorted((run/'receipts').glob('*.json'))
    excluded = set(exclude_families)
    listing = [(p, read(p)) for p in paths]
    listing = [(p, r) for p, r in listing if r['family'] not in excluded]
    if limit is not None:
        listing = listing[:limit]
    if not listing:
        raise ValueError('No new completed families to export')
    out.mkdir(parents=True)
    counts = Counter()
    sources = []
    families = {s: set() for s in ('train', 'validation')}
    buffers = {domain: {s: [] for s in families} for domain in ('belief', 'policy')}
    shards = {domain: [] for domain in buffers}

    def flush(domain, split):
        rows = buffers[domain][split]
        if not rows:
            return
        folder = out/domain; folder.mkdir(exist_ok=True)
        path = folder/f'play-{split}-{len(shards[domain]):06}.npz'
        np.savez_compressed(path, **{k: np.stack([r[k] for r in rows]) for k in rows[0]})
        with np.load(path, allow_pickle=False) as z:
            if any(len(z[k]) != len(rows) for k in z.files):
                raise ValueError('Malformed tensor shard')
        if domain == 'belief':
            load_belief(path)
        shards[domain].append(dict(file=path.name, sha256=sha(path), source='play',
                                   split=split, rows=len(rows)))
        counts[domain+'_'+split] += len(rows)
        rows.clear()

    for number, (receipt_path, receipt) in enumerate(listing, 1):
        episode = run/'episodes'/(receipt_path.stem+'.json.gz')
        if sha(episode) != receipt['episode_sha256']:
            raise ValueError('Episode hash mismatch')
        record = read(episode)
        board = Board.from_dict(record['board'])
        if manifest.get('schema') == 'gen4-component-primary-v1':
            from ops.gen4_component_primary import validate as validate_component
            from bridge_harness.mixed_arena import split as family_split
            validate_component(record, manifest, board, record['index'])
            record = dict(record, split=family_split(record['family']))
        elif manifest.get('protocol') == 'v4-bidder-crossover-v1':
            from ops.v4_runtime import validate_pair as validate_v4
            validate_v4(record, manifest, board, record['index'])
        else:
            validate_pair(record, manifest, board, record['index'])
        family = record['family']; split = record['split']
        if family != deal_key(board.hands, True) or family in set.union(*families.values()):
            raise ValueError('Invalid or duplicate training family')
        if receipt['manifest_identity'] != manifest['identity'] or receipt['index'] != record['index']:
            raise ValueError('Receipt identity mismatch')
        families[split].add(family)
        rows = training_rows(record)
        for domain in buffers:
            buffers[domain][split].extend(rows[domain])
            if len(buffers[domain][split]) >= (4096 if domain == 'belief' else 2048):
                flush(domain, split)
        sources.append(dict(index=record['index'], family=family, split=split, board_id=board.id,
                            pair=record['pair'], manifest_identity=manifest['identity'],
                            episode_sha256=receipt['episode_sha256'], versions=record['versions'],
                            belief_rows=len(rows['belief']), policy_rows=len(rows['policy'])))
        if number % 50 == 0:
            print(json.dumps(dict(exported=number, snapshot_boards=len(listing), flushed_rows=dict(counts))), flush=True)
    for domain in buffers:
        for split in families:
            flush(domain, split)
    (out/'sources.json').write_text(json.dumps(sources, separators=(',', ':'))+'\n')
    provenance = dict(schema='direct-arena-training-export-v1', created_epoch=time.time(),
                      campaign=manifest.get('campaign'), manifest_identity=manifest['identity'],
                      manifest_sha256=sha(run/'manifest.json'), boards=len(sources), counts=dict(counts),
                      families={s: len(v) for s, v in families.items()},
                      source_indices=[r['index'] for r in sources], source_files_sha256=sha(out/'sources.json'),
                      bots=manifest['bots'], source_sha256=manifest['source_sha256'],
                      exporter_sha256=sha(__file__), reference_exporter_sha256=sha(Path(__file__).parents[1]/'scripts/prepare_mixed_training.py'),
                      partial_campaign_snapshot=True, base_training_data_included=False,
                      optimizer_state_included=False, weights_included=False,
                      interpretation='Append these play shards to existing belief and policy training data. '
                      'Deduplicate canonical families against the prior 3,700 and other imports. '
                      'Keep supplied train/validation splits and per-family weights. '
                      'Policy targets are audited local action-minus-reference IMPs, never whole-pair IMPs. '
                      'No legacy or cross-pair IMP pooling. These trained-on families cease to be held-out evidence for v4.')
    (out/'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    for domain, schema in (('belief', SCHEMA), ('policy', 'audited-neural-imp-v1')):
        (out/domain).mkdir(exist_ok=True)
        data = dict(schema=schema, validated=True, shards=shards[domain], counts=dict(counts),
                    families={s: len(v) for s, v in families.items()},
                    parent_sha256=manifest['bots'][manifest['candidate']]['artifact_sha256'][domain],
                    source_files_sha256=sha(out/'sources.json'), source_manifest_sha256=sha(run/'manifest.json'),
                    versions=manifest['bots'], export_only_new_play_shards=True,
                    note='Supplement only: merge with existing base data and selected optimizer state; not a replacement dataset.')
        (out/domain/'dataset.json').write_text(json.dumps(data, indent=2)+'\n')
    (out/'complete.json').write_text(json.dumps(dict(boards=len(sources), source_files_sha256=sha(out/'sources.json')))+'\n')
    return provenance


def pack(out):
    archive = out.with_suffix('.tar.gz')
    with tarfile.open(archive, 'w:gz', compresslevel=6) as tar:
        for path in sorted(out.rglob('*')):
            if path.is_file():
                tar.add(path, arcname=str(path.relative_to(out)), recursive=False)
    chunks = out.parent/(out.name+'-transfer'); chunks.mkdir()
    parts = []
    with archive.open('rb') as f:
        while data := f.read(512*1024):
            path = chunks/f'{archive.name}.part{len(parts):04}'
            path.write_bytes(data)
            parts.append(dict(file=path.name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    info = dict(format='bridge-training-chunks-v1', archive=archive.name,
                size_bytes=archive.stat().st_size, sha256=sha(archive), chunks=parts,
                training=read(out/'provenance.json'))
    (chunks/'manifest.json').write_text(json.dumps(info, indent=2)+'\n')
    print(json.dumps(dict(archive=str(archive), bytes=info['size_bytes'], chunks=len(parts),
                          boards=info['training']['boards'], counts=info['training']['counts'])), flush=True)
    return chunks


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--limit', type=int)
    p.add_argument('--exclude-sources', type=Path, action='append', default=[])
    a = p.parse_args()
    excluded = {r['family'] for path in a.exclude_sources for r in read(path)}
    export(a.run.resolve(), a.out.resolve(), excluded, a.limit)
    pack(a.out.resolve())


if __name__ == '__main__':
    main()
