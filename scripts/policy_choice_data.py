"""Freeze and validate matched branch choices without using hidden inputs.

All positions, rooms and descendants of a canonical deal stay in one split.
Existing validation families are divided into tuning and untouched test sets.
Only the two actually rolled-out alternatives receive a reward label.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[name] = '1'
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.auction_policy import encode_decision
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board, Game, card
from bridge_harness.fork_audit import audited_gain
from bridge_harness.loop_registry import sha
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest

SPLITS = ('train', 'validation', 'test')


def family_split(family):
    bucket = int(family[:8], 16) % 10
    return 'test' if bucket == 0 else 'validation' if bucket == 5 else 'train'


def weights(path):
    with np.load(path, allow_pickle=False) as data:
        return {k: data[k] for k in data.files}


def scores(w, x, mode):
    """Same independent action scorer as deployment, for any candidate count."""
    n = len(x['state'])
    state = np.concatenate([x['state'], w['call_embedding'][x['calls']].reshape(n, -1),
                            w['seat_embedding'][x['seats']].reshape(n, -1)], axis=1)
    h = np.maximum(state @ w['state_hidden_kernel'] + w['state_hidden_bias'], 0)
    z = np.concatenate([x['actions'], np.broadcast_to(h[:, None, :],
                       (n, x['actions'].shape[1], h.shape[1]))], axis=-1)
    for layer in ('action_hidden', 'action_hidden_2'):
        z = np.maximum(z @ w[layer + '_kernel'] + w[layer + '_bias'], 0)
    value = (z @ w['action_score_kernel'] + w['action_score_bias'])[..., 0]
    q_scale = 1. if mode == 'gen3' else float(w.get('rank_q_scale' if mode == 'rank' else 'imp_q_scale', 0.))
    return value + q_scale * x['q']


def validate_event(episode, event):
    a = episode['tables'][event['candidate_table']]
    b = episode['tables'][event['reference_table']]
    ply = event['ply']
    action = a['actions'][ply]
    if event['selection'] != 'independent-random-post-commit' or not action['committed_before_audit'] or not action['audit_draw']:
        raise ValueError('Audit was not drawn after committing the move')
    if [x['card'] for x in a['actions'][:ply]] != [x['card'] for x in b['actions'][:ply]]:
        raise ValueError('Unmatched branch prefix')
    if action['card'] != event['candidate_card'] or b['actions'][ply]['card'] != event['reference_card']:
        raise ValueError('Wrong compared moves')
    if audited_gain(a['ns_score'], b['ns_score'], event['actor']) != event['gain_imps']:
        raise ValueError('Wrong partnership reward sign or IMP conversion')
    if action.get('replayed_prefix') or action.get('counterfactual_forced'):
        raise ValueError('Audit labels a replayed or forced action')
    return action


def extract(runs, out, parent3, parent4):
    if out.exists():
        raise ValueError('Use a new dataset directory')
    out.mkdir(parents=True)
    started = time.time()
    models = {'gen3': weights(parent3), 'gen4': weights(parent4)}
    model4_sha = sha(parent4)
    sources = []
    manifests = []
    for source_id, run in enumerate(runs):
        m = json.loads((run / 'manifest.json').read_text())
        if digest({k: v for k, v in m.items() if k != 'identity'}) != m['identity']:
            raise ValueError('Changed source manifest')
        manifests.append(m)
        for path in sorted((run / 'episodes').glob('*.json.gz')):
            sources.append(dict(source=source_id, path=str(path.resolve())))
    atomic_json(out / 'snapshot.json', dict(created_epoch=started, runs=[str(p.resolve()) for p in runs],
                manifests=manifests, files=sources, model_sha256={'gen3': sha(parent3), 'gen4': model4_sha}))
    buffers = {split: [] for split in SPLITS}
    entries = []
    counts = Counter()
    families = {split: set() for split in SPLITS}
    family_metadata = []
    family_seen = set()
    predicted_error = 0.

    def flush(split):
        nonlocal predicted_error
        rows = buffers[split]
        if not rows:
            return
        data = {key: np.stack([r[key] for r in rows]) for key in rows[0]}
        for name, model in models.items():
            value = scores(model, data, name)
            data[name + '_contrast'] = value[:, 0] - value[:, 1]
        mask = data['current_policy'].astype(bool)
        if mask.any():
            error = float(np.max(np.abs(data['gen4_contrast'][mask] - data['logged_contrast'][mask])))
            predicted_error = max(predicted_error, error)
            if error > 1e-5:
                raise ValueError('Reconstructed Gen4 score disagrees with logged decision: ' + str(error))
        path = out / f'{split}-{len(entries):05d}.npz'
        np.savez_compressed(path, **data)
        entries.append(dict(file=path.name, sha256=sha(path), split=split, rows=len(rows)))
        counts['rows_' + split] += len(rows)
        rows.clear()

    for source_number, source in enumerate(sources):
        raw = Path(source['path']).read_bytes()
        source['sha256'] = hashlib.sha256(raw).hexdigest()
        record = json.loads(gzip.decompress(raw))
        m = manifests[source['source']]
        if record['manifest_identity'] != m['identity']:
            raise ValueError('Episode/manifest mismatch')
        family = record['family']
        if family in family_seen:
            raise ValueError('Duplicate family across frozen source snapshot')
        family_seen.add(family)
        split = family_split(family)
        if (record['split'] == 'validation') != (split != 'train'):
            raise ValueError('Original family partition changed')
        candidate = record['candidate']
        current_policy = m['bots'][candidate]['artifact_sha256'].get('policy') == model4_sha
        seen_states = set()
        family_counts = Counter()
        family_rows = []
        for room, episode in record['unique_tables'].items():
            if episode.get('schema_version') == 'v4-passed-out-v1':
                continue
            if episode['family'] != family or episode['versions'] != record['versions']:
                raise ValueError('Nested identity differs')
            board = Board.from_dict(episode['board'])
            if deal_key(board.hands, True) != family:
                raise ValueError('Canonical family differs from cards')
            events = defaultdict(lambda: defaultdict(list))
            for event in episode['audits']:
                key = 'root' if event['depth'] == 0 else 'recursive'
                family_counts[key + '_audits'] += 1
                if event['identical_action']:
                    if event['candidate_card'] != event['reference_card'] or event['gain_imps'] != 0:
                        raise ValueError('Invalid identical-action label')
                    family_counts[key + '_identical'] += 1
                    continue
                validate_event(episode, event)
                events[event['candidate_table']][event['ply']].append(event)
            for event in episode.get('budget_skips', []):
                key = 'root' if event['depth'] == 0 else 'recursive'
                family_counts[key + '_budget_skips'] += 1
            for table_id, table in enumerate(episode['tables']):
                game = Game(board)
                for ply, action in enumerate(table['actions']):
                    o = game.observation()
                    for event in events[table_id].get(ply, []):
                        if o.actor != event['actor']:
                            raise ValueError('Audit actor differs from replay')
                        key = digest([episode['seed'], episode['board'],
                                      [a['card'] for a in table['actions'][:ply]],
                                      event['candidate_card'], event['reference_card']])
                        if key in seen_states:
                            family_counts['duplicate_audits'] += 1
                            continue
                        seen_states.add(key)
                        x, cards = encode_decision(o, action)
                        valid = x['mask'][0] > 0
                        indices = [int(np.flatnonzero(valid & (cards[0] == card(event[name])))[0])
                                   for name in ('candidate_card', 'reference_card')]
                        row = {k: v[0] for k, v in x.items() if k not in ('mask', 'actions', 'q')}
                        row.update(actions=x['actions'][0, indices].astype(np.int8),
                                   q=x['q'][0, indices].astype(np.float32),
                                   y=np.float32(event['gain_imps']), depth=np.int8(event['depth']),
                                   group=family, source=np.int8(source['source']), pair=record['pair'],
                                   current_policy=np.int8(current_policy),
                                   logged_contrast=np.float32(event.get('expected_gain_imps') or 0.),
                                   eligible_actions=np.int8(valid.sum()), index=np.int32(record['index']))
                        family_rows.append(row)
                    if action['seat'] != 'NESW'[o.actor]:
                        raise ValueError('Wrong replay seat')
                    game.play(card(action['card']))
                if not game.done or game.ns_score() != table['ns_score'] or game.declarer_tricks != table['declarer_tricks']:
                    raise ValueError('Completed continuation score fails replay')
        for row in family_rows:
            row['weight'] = np.float32(1 / len(family_rows))
            buffers[split].append(row)
        if family_rows:
            families[split].add(family)
        family_metadata.append(dict(family=family, split=split, source=source['source'], pair=record['pair'],
                                    current_policy=current_policy, rows=len(family_rows), **family_counts))
        counts.update(family_counts)
        if len(buffers[split]) >= 2048:
            flush(split)
        if (source_number + 1) % 100 == 0:
            progress = dict(files=source_number + 1, total_files=len(sources),
                            emitted_rows=sum(e['rows'] for e in entries), seconds=time.time() - started)
            atomic_json(out / 'progress.json', progress)
            print(json.dumps(progress), flush=True)
    for split in SPLITS:
        flush(split)
    atomic_json(out / 'sources.json', sources)
    atomic_json(out / 'families.json', family_metadata)
    result = dict(schema='paired-policy-choices-v1', validated=True, shards=entries,
                  counts=dict(counts), families={s: len(families[s]) for s in SPLITS},
                  total_families=len(family_seen), model_sha256={'gen3': sha(parent3), 'gen4': model4_sha},
                  source_sha256=sha(out / 'sources.json'), snapshot_sha256=sha(out / 'snapshot.json'),
                  deployment_contrast_max_error=predicted_error,
                  split_rule='int(canonical_family[:8],16)%10: 0 test, 5 validation, all others train; preserves old 80/20 split',
                  interpretation='Two observed alternatives only. Family-grouped; root and recursive results separated. Budget-conditioned audit sample; no inverse propensity correction for unlogged admission probabilities.')
    atomic_json(out / 'dataset.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'shards'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--gen3', type=Path, required=True)
    parser.add_argument('--gen4', type=Path, required=True)
    args = parser.parse_args()
    extract(args.run, args.out, args.gen3, args.gen4)
