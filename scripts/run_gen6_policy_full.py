"""Audit, extract and train the unchanged policy recipe on the pinned full feed.

Keep new confirmation episodes out of extraction until the single candidate is
selected. The width experiment's validation-only trainer uses the same width64,
optimizer and eight-epoch recipe and preserves the complete promoted parent.
"""
import argparse
from collections import Counter
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, d):
    p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_suffix('.tmp')
    t.write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')
    t.replace(p)


def ids(v, out):
    if isinstance(v, str) and len(v) == 64:
        out.add(v)
    elif isinstance(v, dict):
        for k, x in v.items():
            ids(k, out)
            ids(x, out)
    elif isinstance(v, list):
        for x in v:
            ids(x, out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--plan', type=Path, required=True)
    a = ap.parse_args()
    plan = json.loads(a.plan.read_text())
    root = Path(plan['output']); root.mkdir(parents=True, exist_ok=True)
    lock = (root / 'writer.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if (root / 'fit/result.json').exists():
        print('Policy fit already complete; confirmation is a separate remaining step.', flush=True)
        return
    repo = Path(plan['repository']); sys.path.insert(0, str(repo))
    import numpy as np
    from bridge_harness.core import Board
    from bridge_harness.bidding_env import deal_key
    from bridge_harness.runner import replay
    from bridge_harness.training import digest
    from scripts.policy_choice_data import family_split
    from scripts.prepare_outcome_policy import extract
    for entry in plan['verified_files']:
        if sha(Path(entry['path'])) != entry['sha256']:
            raise ValueError('Pinned dependency changed: ' + entry['path'])
    raw = Path(plan['raw']); base = Path(plan['base'])
    base_manifest = json.loads((base / 'dataset.json').read_text())
    base_families = json.loads((base / 'families.json').read_text())
    base_ids = {r['family'] for r in base_families}
    reserved = set()
    for p in plan['reserved_json']:
        value = json.loads(Path(p).read_text())
        # A data manifest also lists its historical training sources. Only its
        # explicit reservation field denotes evaluation families.
        if isinstance(value, dict) and 'reserved_families' in value:
            value = value['reserved_families']
        ids(value, reserved)
    for name in plan['reserved_datasets']:
        p = Path(name)
        for e in json.loads(p.read_text())['shards']:
            shard = Path(e['file'])
            if not shard.is_absolute(): shard = p.parent / shard
            assert sha(shard) == e['sha256']
            with np.load(shard, allow_pickle=False) as z:
                reserved.update(map(str, z['split_group']))
    if reserved & {r['family'] for r in base_families if r['split'] == 'train'}:
        raise ValueError('Explicit reservation overlaps historical training; reconcile before fit')
    audit_path = root / 'audit.json'
    eligible = root / 'eligible-raw'
    if not audit_path.exists():
        eligible.mkdir(exist_ok=True); (eligible / 'episodes').mkdir(exist_ok=True)
        manifest = json.loads((raw / 'manifest.json').read_text())
        assert digest({k: v for k, v in manifest.items() if k != 'identity'}) == manifest['identity']
        shutil.copyfile(raw / 'manifest.json', eligible / 'manifest.json')
        receipts = json.loads((raw / 'receipts.json').read_text())
        assert len(receipts) == plan['source_records']
        counts = Counter(); fresh = []; seen = set()
        previous = {r['family'] for r in json.loads(Path(plan['previous_families']).read_text())}
        for i, r in enumerate(receipts, 1):
            path = raw / 'episodes' / f"{r['index']:06d}.json.gz"
            assert sha(path) == r['episode_sha256']
            e = json.loads(gzip.decompress(path.read_bytes()))
            f = e['family']; assert f == r['family'] and f not in seen
            seen.add(f)
            assert deal_key(Board.from_dict(e['board']).hands, True) == f
            assert e['manifest_identity'] == manifest['identity']
            split = family_split(f)
            assert e['split'] == ('train' if split == 'train' else 'validation')
            for actor in (e['candidate'], e['opponent']):
                bot = manifest['bots'][actor]; h = bot.get('artifact_sha256', {}).get('policy')
                if h in plan['excluded_policy_sha256'] or (bot.get('policy') and not h):
                    raise ValueError('Excluded or unidentified actor: ' + actor)
            if f in reserved or f in base_ids:
                counts['excluded_reserved_or_existing'] += 1
                continue
            if split == 'test':
                fresh.append(dict(family=f, index=e['index'], previously_inspected=f in previous))
                counts['test_reserved'] += 1
                continue
            for room in e['unique_tables'].values():
                assert deal_key(Board.from_dict(room['board']).hands, True) == f
                if room.get('schema_version') == 'v4-passed-out-v1':
                    assert Board.from_dict(room['board']).contract is None
                    assert all(not t['actions'] and t['ns_score'] == 0 for t in room['tables'])
                    counts['verified_passed_out_rooms'] += 1
                    continue
                # Passed-out records have no moves; played records must finish
                # and reproduce every logged score, even if status is omitted.
                tables = [dict(t, status='ok') for t in room['tables']]
                replay(dict(room, tables=tables))
                counts['legally_replayed_tables'] += len(room['tables'])
            dest = eligible / 'episodes' / path.name
            if not dest.exists(): dest.symlink_to(path.resolve())
            counts[split + '_families'] += 1
            if i % 100 == 0:
                print(json.dumps(dict(stage='policy_audit', completed=i, total=len(receipts), counts=dict(counts))), flush=True)
        save(root / 'confirmation-families.json', fresh)
        save(audit_path, dict(feed_commit=plan['feed_commit'], source_records=len(receipts), counts=dict(counts),
            fresh_confirmation_families=sum(not f['previously_inspected'] for f in fresh),
            test_evaluated=False, plan_sha256=sha(a.plan), script_sha256=sha(Path(__file__))))
    new = root / 'new-data'
    if not (new / 'dataset.json').exists():
        if new.exists():
            new.rename(root / ('interrupted-extraction-' + str(time.time_ns())))
        extract([eligible], new, Path(plan['feature_parent']), Path(plan['legacy_comparator']))
    union = root / 'union'
    if not (union / 'dataset.json').exists():
        union.mkdir(exist_ok=True)
        counts = Counter(); families = []; shards = []; sources = []; manifests = []
        used = set()
        for number, folder in enumerate((base, new)):
            md = json.loads((folder / 'dataset.json').read_text())
            ff = json.loads((folder / 'families.json').read_text())
            if used & {f['family'] for f in ff}:
                raise ValueError('Duplicate family across pools')
            used.update(f['family'] for f in ff)
            # Historical test files remain frozen; training never opens them.
            for e in md['shards']:
                p = folder / e['file']; assert sha(p) == e['sha256']
                name = f'pool{number}-' + e['file']; dst = union / name
                if not dst.exists(): dst.symlink_to(p.resolve())
                shards.append(dict(e, file=name))
            counts.update(md['counts']); families += ff
            sources.append(dict(path=str(folder), dataset_sha256=sha(folder / 'dataset.json')))
            manifests.append(md)
        save(union / 'families.json', families)
        save(union / 'sources.json', sources)
        save(union / 'snapshot.json', dict(plan=plan, audit=json.loads(audit_path.read_text()), source_datasets=sources))
        md = dict(base_manifest, shards=shards, counts=dict(counts),
            families=dict(Counter(f['split'] for f in families)), total_families=len(families),
            source_sha256=sha(union / 'sources.json'), snapshot_sha256=sha(union / 'snapshot.json'),
            training_parent_sha256=sha(Path(plan['parent'])), initial_partial_snapshot=False)
        save(union / 'dataset.json', md)
        print(json.dumps(dict(stage='full_policy_union_ready', counts=dict(counts), families=md['families'])), flush=True)
    fit = root / 'fit'
    if fit.exists() and not (fit / 'training.json').exists():
        fit.rename(root / ('interrupted-pre-epoch-' + str(time.time_ns())))
    command = [sys.executable, '-u', str(repo / 'scripts/train_clean_policy_v5.py'),
        '--data', str(union), '--out', str(fit), '--parent', plan['parent'],
        '--rank-candidate', plan['parent'], '--previous-families', plan['previous_families'],
        '--mode', 'attention', '--attention-width', '64', '--epochs', '8',
        '--validation-only', '--comparison-checkpoint', plan['parent']]
    print(json.dumps(dict(stage='policy_training', command=command)), flush=True)
    subprocess.run(command, cwd=repo, check=True, env=os.environ.copy())
    save(root / 'status.json', dict(stage='fit_complete_confirmation_pending', test_evaluated=False,
        result=str(fit / 'result.json'), promoted=False))


if __name__ == '__main__':
    main()
