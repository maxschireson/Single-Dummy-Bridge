"""Freeze and verify the five physical Gen5 arena archives already on GitHub.

The output is an index of immutable raw records, not an extracted training set.
Run with the current Gen5 runtime; replay never invokes a player or DDS.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.mixed_arena import split
from bridge_harness.training import digest
from ops.gen5_runtime import validate

SOURCES = [
    ('gen5-initial', '5', 'gen5-publication', 'arena-gen5-codex-feed'),
    ('gen5-corrected', '5', 'gen5-32-publication', 'arena-gen5-codex-32-feed'),
    ('gen5r', '5R', 'gen5r-publication', 'arena-gen5r-feed'),
    ('gen5rz-initial', '5RZ', 'gen5rz-publication', 'arena-gen5rz-feed'),
    ('gen5rz-ben', '5RZ', 'gen5rz-ben-publication', 'arena-gen5rz-ben-feed'),
]
BAD_POLICY = 'e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_blob(raw):
    return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def checked_file(root, path, tree):
    raw = (root / path).read_bytes()
    if git_blob(raw) != tree[path]:
        raise ValueError(f'Local file differs from published Git blob: {path}')
    return raw


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def verify_record(record, receipt, manifest):
    if record['schema'] != 'gen5-two-auction-arena-v1':
        raise ValueError('Unexpected parent schema')
    validate(record, manifest, record['index'])  # All main/branch legal replays, scores, auctions and seats.
    family = deal_key(Board.from_dict(record['board']).hands, True)
    if record['family'] != family or record['split'] != split(family):
        raise ValueError('Parent family/split mismatch')
    for key in ('index', 'family', 'split', 'pair', 'manifest_identity', 'completed_epoch'):
        if receipt[key] != record[key]:
            raise ValueError(f'Receipt metadata mismatch: {key}')
    counts = Counter(records=1)
    actor_bots = {'candidate': record['candidate'], 'opponent': record['opponent']}
    for bot in actor_bots.values():
        if manifest['bots'][bot].get('artifact_sha256', {}).get('policy') == BAD_POLICY:
            raise ValueError('Banned Gen4 policy participant')
    for game in record['unique_tables'].values():
        counts['root_games'] += 1
        if game.get('status') != 'ok':
            raise ValueError('Incomplete root game')
        if deal_key(Board.from_dict(game['board']).hands, True) != family:
            raise ValueError('Root game family mismatch')
        if game.get('schema_version') == 'v4-passed-out-v1':
            if game['board']['contract'] is not None or any(
                    t['actions'] or t['ns_score'] != 0 for t in game['tables']):
                raise ValueError('Invalid passed-out record')
            counts['passed_out_games'] += 1
            counts['tables'] += len(game['tables'])
            continue
        if game['family'] != family or game['split'] != record['split']:
            raise ValueError('Root provenance mismatch')
        if game['versions'] != record['versions']:
            raise ValueError('Root versions mismatch')
        for table in game['tables']:
            if table.get('status') != 'ok' or len(table['actions']) != 52:
                raise ValueError('Incomplete cardplay table')
            if not 0 <= table['declarer_tricks'] <= 13:
                raise ValueError('Invalid final trick count')
            counts['tables'] += 1
            counts['tables_with_final_tricks'] += 1
            for action in table['actions']:
                counts['actions'] += 1
                spec = manifest['bots'][actor_bots[action['player']]]
                estimates = action.get('estimates')
                if estimates:
                    counts['actions_with_pimc'] += 1
                    for value in estimates.values():
                        if not all(math.isfinite(value[k]) for k in
                                   ('utility', 'gap_to_best', 'declarer_tricks')):
                            raise ValueError('Non-finite PIMC estimate')
                    if action['card'] not in estimates:
                        raise ValueError('Chosen action absent from PIMC estimates')
                    for c, probability in action.get('proposal_probabilities', {}).items():
                        if probability > 0 and c not in estimates:
                            raise ValueError('Proposal action absent from PIMC estimates')
                elif any(action.get(k) for k in ('forced', 'counterfactual_forced',
                                                'fixed_opening_lead', 'replayed_prefix')):
                    counts['forced_or_replayed_actions_without_pimc'] += 1
                elif spec.get('engine') == 'ben':
                    counts['ben_actions_without_harness_pimc'] += 1
                else:
                    raise ValueError('Non-forced harness decision missing PIMC estimates')
    if counts['root_games'] != receipt['root_games'] or counts['tables'] != receipt['tables']:
        raise ValueError('Receipt game/table counts mismatch')
    return counts


def audit(publications_root, out):
    if out.exists():
        raise ValueError('Refusing to overwrite a frozen handoff')
    out.mkdir(parents=True)
    refs = [row[3] for row in SOURCES]
    remote = git(publications_root / SOURCES[0][2], 'ls-remote', '--heads', 'origin', *refs)
    commits = {line.split()[1].removeprefix('refs/heads/'): line.split()[0]
               for line in remote.decode().splitlines()}
    sources, totals, groups, all_families = [], Counter(), Counter(), {}
    for source_id, group, directory, branch in SOURCES:
        root = publications_root / directory
        commit = commits[branch]
        tree = {}
        for entry in git(root, 'ls-tree', '-r', '-z', commit, 'recovery').split(b'\0'):
            if not entry:
                continue
            meta, path = entry.decode().split('\t', 1)
            tree[path] = meta.split()[2]
        manifest_raw = checked_file(root, 'recovery/manifest.json', tree)
        manifest = json.loads(manifest_raw)
        if digest({k: v for k, v in manifest.items() if k != 'identity'}) != manifest['identity']:
            raise ValueError('Manifest identity mismatch')
        for spec in manifest['bots'].values():
            if digest({k: v for k, v in spec.items() if k != 'identity'}) != spec['identity']:
                raise ValueError('Bot identity mismatch')
        corpus_raw = checked_file(root, 'recovery/corpus.jsonl', tree)
        if sha(corpus_raw) != manifest['corpus_sha256']:
            raise ValueError('Corpus digest mismatch')
        corpus = [json.loads(line) for line in corpus_raw.splitlines() if line]
        dest = out / 'sources' / source_id
        dest.mkdir(parents=True)
        (dest / 'manifest.json').write_bytes(manifest_raw)
        inventory, counts, splits, pairs = [], Counter(), Counter(), Counter()
        paths = sorted(path for path in tree if path.startswith('recovery/episodes/')
                       and path.endswith('.json.gz'))
        for number, path in enumerate(paths, 1):
            raw = checked_file(root, path, tree)
            receipt_path = path.replace('/episodes/', '/receipts/').removesuffix('.gz')
            receipt_raw = checked_file(root, receipt_path, tree)
            receipt = json.loads(receipt_raw)
            if sha(raw) != receipt['episode_sha256']:
                raise ValueError(f'Episode digest mismatch: {path}')
            record = json.loads(gzip.decompress(raw))
            index = record['index']
            if Path(path).name != f'{index:06d}.json.gz':
                raise ValueError('Episode index/filename mismatch')
            if deal_key(Board.from_dict(corpus[index]).hands, True) != record['family']:
                raise ValueError('Episode/corpus family mismatch')
            record_counts = verify_record(record, receipt, manifest)
            family = record['family']
            if family in all_families:
                raise ValueError(f'Family duplicated between phases: {family}')
            all_families[family] = record['split']
            counts.update(record_counts)
            counts['compressed_episode_bytes'] += len(raw)
            splits[record['split']] += 1
            pairs[record['pair']] += 1
            inventory.append(dict(index=index, family=family, source_split=record['split'],
                                  pair=record['pair'], completed_epoch=record['completed_epoch'],
                                  episode=path, episode_sha256=sha(raw), episode_git_blob=tree[path],
                                  receipt=receipt_path, receipt_sha256=sha(receipt_raw),
                                  receipt_git_blob=tree[receipt_path], counts=dict(record_counts)))
            if number % 250 == 0 or number == len(paths):
                print(f'{source_id}: {number}/{len(paths)} full records verified', flush=True)
        inventory_raw = b''.join((json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n').encode()
                                 for row in inventory)
        inventory_path = dest / 'inventory.jsonl.gz'
        inventory_path.write_bytes(gzip.compress(inventory_raw, mtime=0))
        metadata = dict(source_id=source_id, group=group, branch=branch, commit=commit,
                        committed_utc=git(root, 'show', '-s', '--format=%cI', commit).decode().strip(),
                        manifest_identity=manifest['identity'], manifest_sha256=sha(manifest_raw),
                        manifest='recovery/manifest.json', corpus='recovery/corpus.jsonl',
                        corpus_sha256=sha(corpus_raw),
                        inventory=str(inventory_path.relative_to(out)),
                        inventory_sha256=sha(inventory_path.read_bytes()), counts=dict(counts),
                        source_splits=dict(splits), pairs=dict(pairs),
                        last_completed_epoch=max(row['completed_epoch'] for row in inventory),
                        live=source_id == 'gen5rz-ben')
        sources.append(metadata)
        totals.update(counts)
        groups[group] += len(paths)
    handoff = dict(schema='gen6-arena-handoff-v1', repository='maxschireson/Single-Dummy-Bridge',
                   created_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
                   counts=dict(totals), records_by_generation_variant=dict(groups),
                   unique_families=len(all_families), bad_policy_records=0,
                   excluded_policy_sha256=[BAD_POLICY],
                   verified=['Published Git blob identity for every manifest, corpus, episode and receipt',
                             'Compressed episode SHA256, decompression, schema, canonical family and source split',
                             'Participant identities, schedule, bidding conditions and swapped partnerships',
                             'Every completed main and branch table: legal replay, final score and trick count',
                             'Finite PIMC estimates on every non-forced harness decision',
                             'No banned Gen4 policy participants; no duplicate family between source phases'],
                   training_split_status='Source splits preserved. Trainer must union all historical and later reserved evaluation/audit families before assigning training splits.',
                   live_feed='arena-gen5rz-ben-feed continues publishing new complete records; each fit must pin and audit its own immutable cutoff.',
                   statistics_exclusions='The first Gen5 phase includes 102 historical-opponent boards excluded from dashboard statistics by sample-budget policy; retain their raw records for training.',
                   speed_comparisons={'5RZ32_vs_5RZ16': 'cancelled_by_user',
                                      '5R16_vs_5-32': 'cancelled_by_user'})
    write_json(out / 'manifest.json', handoff)
    print(json.dumps(dict(counts=dict(totals), groups=dict(groups), sources=len(sources))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publications-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    audit(args.publications_root, args.out)
