#!/usr/bin/env python3
"""Export and replay-audit the final pre-migration direct-match snapshot."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import zipfile

RUN = 'workspace/scratch/a1f2b806f0ac/bridge-arena/runs/mixed-fork-25k/g0001-direct/'
CODE = 'workspace/scratch/a1f2b806f0ac/bridge-direct/'
EXPECTED_ID = '8373b7b6adc88bb1cd3755840bb961797a61e47d9d8fbac79d1f81bf3cf8227f'
DATASET_ID = 'gen3-direct-pre-migration-2026-11-09-465'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def run(archive, output):
    from scipy.stats import t
    with zipfile.ZipFile(archive) as z, tempfile.TemporaryDirectory() as temp:
        hashes = json.loads(z.read('FILE_SHA256.json'))
        checked = set()

        def read_checked(name):
            data = z.read(name)
            if sha(data) != hashes[name]:
                raise ValueError(f'Archived checksum mismatch: {name}')
            checked.add(name)
            return data

        for name in z.namelist():
            if name.startswith(CODE + 'bridge_harness/') and name.endswith('.py'):
                relative = Path(name[len(CODE):])
                if '..' in relative.parts:
                    raise ValueError('Invalid source path')
                target = Path(temp) / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(read_checked(name))
        sys.path.insert(0, temp)
        from bridge_harness.core import Board
        from bridge_harness.direct_arena import validate_pair, compact
        from bridge_harness.training import digest

        manifest_bytes = read_checked(RUN + 'manifest.json')
        manifest = json.loads(manifest_bytes)
        if manifest['identity'] != EXPECTED_ID:
            raise ValueError('Unexpected source cohort')
        if digest({k: v for k, v in manifest.items() if k != 'identity'}) != EXPECTED_ID:
            raise ValueError('Source manifest identity mismatch')
        corpus_bytes = read_checked(RUN + manifest['corpus'])
        if sha(corpus_bytes) != manifest['corpus_sha256']:
            raise ValueError('Frozen corpus changed')
        corpus = [json.loads(line) for line in corpus_bytes.splitlines()]
        handoff = json.loads(read_checked(RUN + 'migration-handoff.json'))
        original_state = json.loads(read_checked(RUN + 'state.json'))
        for spec in manifest['bots'].values():
            for key, expected in spec['artifact_sha256'].items():
                if sha(read_checked(RUN + spec[key])) != expected:
                    raise ValueError('Frozen model changed')
        if sha(read_checked(CODE + 'bridge_harness/libbridge_dds.so')) != handoff['dds_sha256']:
            raise ValueError('Archived DDS binary changed')

        names = sorted(n for n in z.namelist()
                       if n.startswith(RUN + 'episodes/') and n.endswith('.json.gz'))
        if len(names) != 465:
            raise ValueError('Expected exactly 465 direct pairs')
        rows = []
        replayed_tables = 0
        for index, name in enumerate(names):
            if name != RUN + f'episodes/{index:06d}.json.gz':
                raise ValueError('Missing or duplicated direct index')
            data = read_checked(name)
            episode = json.loads(gzip.decompress(data))
            validate_pair(episode, manifest, Board.from_dict(corpus[index]), index)
            receipt = json.loads(read_checked(RUN + f'receipts/{index:06d}.json'))
            expected = dict(compact(episode), episode_sha256=sha(data),
                            manifest_identity=EXPECTED_ID)
            if receipt != expected:
                raise ValueError(f'Receipt mismatch: {index}')
            replayed_tables += sum(len(episode[k]['tables']) for k in ('focal', 'control'))
            rows.append({
                'index': index, 'family': episode['family'], 'pair': episode['pair'],
                'imps': episode['imps'], 'score_difference': episode['score_difference'],
                'focal_ns_score': episode['focal']['tables'][0]['ns_score'],
                'control_ns_score': episode['control']['tables'][0]['ns_score'],
                'split': episode['split'], 'completed_epoch': episode['completed_epoch'],
                'episode_sha256': sha(data),
            })
        if len({r['family'] for r in rows}) != 465:
            raise ValueError('Duplicate canonical deal family')

        groups = {}
        for pair in ('AB', 'AC', 'BC'):
            values = [r['imps'] for r in rows if r['pair'] == pair]
            n = len(values)
            total = sum(values)
            sum_squares = sum(v * v for v in values)
            mean = total / n
            variance = (sum_squares - total * total / n) / (n - 1)
            sd = math.sqrt(variance)
            se = sd / math.sqrt(n)
            half = float(t.ppf(.975, n - 1)) * se
            group = dict(n=n, total=total, sum_squares=sum_squares, mean=mean,
                         variance=variance, sd=sd, se=se, ci=[mean - half, mean + half],
                         wins=sum(v > 0 for v in values), ties=sum(v == 0 for v in values),
                         losses=sum(v < 0 for v in values),
                         imp_histogram={str(k): v for k, v in sorted(Counter(values).items())})
            old = original_state['by_pair'][pair]
            if (n, total, group['wins'], group['ties'], group['losses']) != (
                    old['boards'], old['imps'], old['wins'], old['ties'], old['losses']):
                raise ValueError(f'Original summary disagrees: {pair}')
            if max(abs(a - b) for a, b in zip(group['ci'], old['descriptive_95_ci'])) > 1e-10:
                raise ValueError(f'Original confidence interval disagrees: {pair}')
            groups[pair] = group

        output.mkdir(parents=True, exist_ok=True)
        ledger = ''.join(json.dumps(r, separators=(',', ':')) + '\n' for r in rows).encode()
        (output / 'pairs.jsonl').write_bytes(ledger)
        (output / 'source-manifest.json').write_bytes(manifest_bytes)
        summary = {
            'schema': 'bridge-historical-head-to-head-v1', 'dataset_id': DATASET_ID,
            'campaign': 'g0001-direct', 'manifest_identity': EXPECTED_ID,
            'protocol': manifest['protocol'], 'score_direction': 'Positive favors first letter in pair.',
            'score_unit': 'One paired board = two swapped-partnership root tables.',
            'score_formula': 'IMP(focal root NS score - control root NS score)',
            'completed': 465, 'contiguous': 465, 'source_index_range_inclusive': [0, 464],
            'versions': manifest['direct_versions'], 'labels': {'A': 'Gen 3.5', 'B': 'Gen 3', 'C': 'Gen 2'},
            'models': {label: manifest['bots'][name] for label, name in manifest['direct_versions'].items()},
            'groups': groups,
            'source': {
                'archive_name': archive.name, 'archive_size_bytes': archive.stat().st_size,
                'archive_sha256': hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest(),
                'manifest_sha256': sha(manifest_bytes), 'corpus_sha256': manifest['corpus_sha256'],
                'source_sha256': manifest['source_sha256'], 'dds_sha256': handoff['dds_sha256'],
                'runtime_sha256': manifest['runtime_sha256'], 'migration_drained_utc': utc(handoff['epoch']),
                'first_completed_utc': utc(min(r['completed_epoch'] for r in rows)),
                'last_completed_utc': utc(max(r['completed_epoch'] for r in rows)),
            },
            'ledger': {'path': 'pairs.jsonl', 'sha256': sha(ledger), 'size_bytes': len(ledger),
                       'rows': 465, 'order': 'source index ascending',
                       'record_identity': ['manifest_identity from summary', 'index from row'],
                       'cross_campaign_overlap_key': 'family (canonical deal-family hash)'},
            'excluded': {
                'legacy_substitution_pairs': 3235,
                'other_bidder_cohorts': True,
                'partial_snapshots_of_these_same_465_pairs': True,
                'counterfactual_audit_forks': True,
                'new_campaign_records': True,
            },
            'aggregation': {
                'additive_fields': ['n', 'total', 'sum_squares', 'wins', 'ties', 'losses'],
                'mean': 'total / n', 'variance': '(sum_squares - total*total/n) / (n-1)',
                'se': 'sqrt(variance/n)', 'ci': 'mean +/- t.ppf(0.975,n-1)*se',
                'requirements': [
                    'Import this dataset once; do not add earlier partial checkpoints again.',
                    'Combine only within the same matchup and verified model/configuration semantics.',
                    'Check canonical family overlap with the new campaign before treating rows as independent.',
                    'Retain source cohort labels; a resumed or fresh run may restart its local indices at zero.',
                    'Use the ledger for rolling windows and curves; append historical source indices before new ones.',
                    'Keep historical head-to-head counts separate from live progress, throughput and training rows.',
                ],
                'confidence_interpretation': 'Descriptive Student-t intervals, unadjusted for repeated looks or multiple matchups.',
            },
        }
        write_json(output / 'summary.json', summary)
        write_json(output / 'validation.json', {
            'dataset_id': DATASET_ID, 'validated_utc': datetime.now(timezone.utc).isoformat(),
            'direct_pairs': 465, 'root_tables': 930, 'all_replayed_tables_including_audits': replayed_tables,
            'archived_files_sha256_verified': len(checked), 'unique_families': 465,
            'all_465_receipts_match_recomputed_episode_compact_records': True,
            'frozen_manifest_corpus_models_and_dds_verified': True,
            'swapped_assignments_controllers_legal_replays_and_root_imp_scores_verified': True,
            'all_three_groups_match_archived_final_state': True,
            'partial_snapshots_not_added': True,
        })
        print(json.dumps({'groups': groups, 'ledger_bytes': len(ledger), 'replayed_tables': replayed_tables}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.archive, args.output)
