"""Frozen post-checkpoint paired play test; exact DDS cache and resumable episodes."""
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge_harness.bidding_env import deal_key
from bridge_harness.core import Board
from bridge_harness.improvement import bounded_map, read, validate_record, writer_lock
from bridge_harness.loop_registry import freeze_bot, sha, verify_bot
from bridge_harness.runner import isolated_pair
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest


def initialize(out, study, collection, count, samples, cohort_from=None, exclude_cohort=None, collection_registry=None):
    import numpy as np
    result = read(study/'large/result.json')
    weights = Path(result['selected_weights'])
    assert result['complete'] and sha(weights) == result['selected_sha256']
    cutoff = weights.stat().st_mtime
    data = study/'data'
    # Exclude all training AND model-selection families, including rotations.
    blocked = {e['family'] for e in read(data/'play-provenance.json')}
    if exclude_cohort:
        blocked.update(e['family'] for e in read(exclude_cohort)['boards'])
    for groups in read(data/'bidding-reserved-families.json').values():
        blocked.update(groups)
    legacy = read(data/'bidding-dataset.json')['legacy']
    old_groups = set()
    for split in ('train', 'validation'):
        source = Path(legacy[split]['path'])
        assert sha(source) == legacy[split]['sha256']
        with np.load(source, allow_pickle=False) as z:
            old_groups.update(map(str, np.unique(z['split_group'])))
    captured = {e['path'] for e in read(data/'input-files.json')}
    rows = {}
    excluded = Counter()
    for source in sorted((collection/'g1/selfplay').glob('*/episodes/*.json.gz')):
        if source.stat().st_mtime <= cutoff:
            continue
        if str(source) in captured:
            excluded['captured_source'] += 1
            continue
        record = read(source)
        if record.get('status') != 'ok':
            excluded['incomplete'] += 1
            continue
        board = Board.from_dict(record['board'])
        family = deal_key(board.hands, True)
        if family in blocked or any(digest(board.hands[j:]+board.hands[:j]) in old_groups for j in range(4)):
            excluded['train_or_validation_family'] += 1
            continue
        if not board.contract:
            excluded['passed_out'] += 1
            continue
        rows.setdefault(family, dict(family=family, board=board.to_dict(),
            source=str(source), source_sha256=sha(source), source_completed_epoch=source.stat().st_mtime))
    # Selection is independent of outcomes; freeze once, never top up after seeing scores.
    selected = sorted(rows.values(), key=lambda e:digest(['large-belief-pilot-v1', e['family']]))[:count]
    if cohort_from is not None:
        cohort = read(cohort_from)
        assert cohort['dataset_sha256'] == sha(data/'dataset.json')
        assert cohort['selected_belief_sha256'] == result['selected_sha256']
        selected = cohort['boards']
        assert all(e['family'] in rows for e in selected)
    if len(selected) != count:
        raise ValueError(f'Only {len(selected)} eligible post-checkpoint deals; requested {count}')
    original = collection/'bots/v2/bot.json'
    parent = read(original)
    bots = {}
    for name, factory, belief in (
        ('incumbent', 'bridge_harness.combined_player:CombinedPlayer', original.parent/'artifacts/belief.npz'),
        ('large', 'bridge_harness.public_belief_player:PublicBeliefPlayer', weights)):
        spec = copy.deepcopy(parent['spec'])
        spec['factory'] = factory
        spec['artifacts'] = dict(belief=str(belief), policy=str(original.parent/'artifacts/policy.npz'))
        assert spec['kwargs']['exploration'] == 0
        spec['kwargs']['samples'] = samples
        spec['budget']['samples'] = samples
        bots[name] = str(freeze_bot(out, name, spec))
    manifest = dict(schema=1, created_utc=datetime.now(timezone.utc).isoformat(),
        count=count, eligible_pool=len(rows), exclusions=dict(excluded), bots=bots,
        selected_belief_sha256=result['selected_sha256'], selected_epoch=result['best_epoch'],
        checkpoint_epoch=cutoff, dataset_sha256=sha(data/'dataset.json'),
        source_incumbent_identity=parent['identity'], boards=selected,
        seed=2026110903, samples=samples, exploration=0, near_tie=.125,
        methodology='Two tables per deal: candidate NS/incumbent EW and reverse; same auction and RNG group. Positive IMP favors candidate. No training or selection-validation family. Existing exploration outcomes are not used as controls.',
        interpretation=f'Fixed {count}-deal initial diagnostic, not a significance or promotion gate. Report all outcomes; no model changes or outcome-based stopping.',
        promotion='No automatic promotion. Candidate remains separately identified.')
    if collection_registry:
        promotion=read(collection_registry)
        assert promotion['status']=='promoted-for-collection'
        assert promotion['samples']==samples
        assert promotion['collector_identity']==read(bots['large'])['identity']
        assert promotion['reference_identity']==read(bots['incumbent'])['identity']
        manifest.update(purpose='mixed-pool-collection',promotion=promotion,
            interpretation='Frozen-version paired collection block. Outcomes supply strength evidence before later training reuse; IMP significance is not a promotion prerequisite.')
    atomic_json(out/'manifest.json', manifest)
    return manifest


def config(manifest, board):
    return dict(mode='partnership', candidate='manifest:'+manifest['bots']['large'],
        baseline='manifest:'+manifest['bots']['incumbent'], common='manifest:'+manifest['bots']['incumbent'],
        objective='tricks', rng_group='large-belief-common-worlds-v1',
        seed=int(digest([manifest['seed'], board.id, 'decision'])[:12], 16))


def report(out, manifest):
    import numpy as np
    from scipy.stats import t
    records = []
    for row in manifest['boards']:
        path = out/'episodes'/f"{row['family']}.json.gz"
        if path.exists():
            board = Board.from_dict(row['board'])
            r = read(path)
            validate_record(r, board, config(manifest, board))
            records.append(r)
    values = np.array([r['imps'] for r in records], dtype=float)
    totals = Counter()
    for r in records:
        for table in r['tables']:
            for action in table['actions']:
                for field in ('dds_calls', 'dds_native_solves', 'dds_cache_hits', 'dds_duplicate_worlds'):
                    totals[field] += action.get(field, 0)
    n = len(values)
    mean = float(values.mean()) if n else None
    half = float(t.ppf(.975, n-1)*values.std(ddof=1)/np.sqrt(n)) if n > 1 else None
    tricks = np.array([(1 if r['board']['declarer'] in ('N','S') else -1)*
        (r['tables'][0]['declarer_tricks']-r['tables'][1]['declarer_tricks']) for r in records], dtype=float)
    trick_mean = float(tricks.mean()) if n else None
    trick_sd = float(tricks.std(ddof=1)) if n > 1 else None
    trick_half = float(t.ppf(.975,n-1)*trick_sd/np.sqrt(n)) if n > 1 else None
    completed_epoch = max((f.stat().st_mtime for f in (out/'episodes').glob('*.json.gz')),default=None)
    elapsed = completed_epoch-datetime.fromisoformat(manifest['created_utc']).timestamp() if completed_epoch else None
    summary = dict(completed=n, target=manifest['count'], complete=n==manifest['count'],
        mean_imps=mean, descriptive_95_ci=None if half is None else [mean-half, mean+half],
        mean_tricks=trick_mean, tricks_sd=trick_sd,
        tricks_descriptive_95_ci=None if trick_half is None else [trick_mean-trick_half,trick_mean+trick_half],
        rough_pairs_for_0p01_trick_80pct_power=(1.96+.842)**2*trick_sd**2/.01**2 if trick_sd is not None else None,
        elapsed_to_last_completion=elapsed, paired_deals_per_minute=60*n/elapsed if elapsed else None,
        wins=int((values>0).sum()), ties=int((values==0).sum()), losses=int((values<0).sum()),
        tables=2*n, cache=dict(totals), epoch=time.time(),
        caution='Deal-paired t interval is descriptive; interim looks are not promotion evidence. Small pilot cannot establish a small strength gain.')
    atomic_json(out/'progress.json', summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, default=ROOT/'runs/large-belief-play-16-v1')
    p.add_argument('--study', type=Path, default=Path('/workspace/scratch/9357bfc2ac0b/bridge-belief-sizes/runs/belief-sizes-v1'))
    p.add_argument('--collection', type=Path, default=Path('/workspace/scratch/e4c61f75d346/bridge-loop/runs/v2-loop-001'))
    p.add_argument('--count', type=int, default=50)
    p.add_argument('--samples', type=int, default=16)
    p.add_argument('--cohort-from', type=Path)
    p.add_argument('--exclude-cohort', type=Path)
    p.add_argument('--collection-registry', type=Path)
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--run-seconds', type=float, default=240)
    p.add_argument('--report-only', action='store_true')
    a = p.parse_args()
    a.out = a.out.resolve(); a.out.mkdir(parents=True, exist_ok=True)
    # One cache across budgets: exact overlapping worlds can be reused safely.
    os.environ.setdefault('BRIDGE_DDS_CACHE', str(ROOT/'runs/large-belief-play-v1/dds-positions.sqlite'))
    with writer_lock(a.out):
        manifest = read(a.out/'manifest.json') if (a.out/'manifest.json').exists() else initialize(a.out,a.study,a.collection,a.count,a.samples,a.cohort_from,a.exclude_cohort,a.collection_registry)
        assert manifest['samples'] == a.samples, 'Use the frozen sample budget for this run'
        for path in manifest['bots'].values():
            verify_bot(path)
        if not a.report_only:
            until = time.monotonic()+a.run_seconds
            def jobs():
                for row in manifest['boards']:
                    if time.monotonic() >= until:
                        break
                    dest = a.out/'episodes'/f"{row['family']}.json.gz"
                    if not dest.exists():
                        yield row
            def work(row):
                board = Board.from_dict(row['board']); cfg = config(manifest,board)
                failed = a.out/'failures'/f"{row['family']}.json.gz"
                if failed.exists():
                    raise RuntimeError(f'Unresolved previous failure: {failed}')
                r = isolated_pair(board,cfg,deadline=300)
                if r['status'] != 'ok':
                    atomic_json(failed,r,compressed=True)
                    raise RuntimeError(f"Arena failure {board.id}: {r.get('error')}")
                validate_record(r,board,cfg)
                atomic_json(a.out/'episodes'/f"{row['family']}.json.gz",r,compressed=True)
                return row['family']
            for family in bounded_map(work,jobs(),a.workers):
                print(json.dumps(report(a.out,manifest)),flush=True)
        print(json.dumps(report(a.out,manifest)),flush=True)


if __name__ == '__main__':
    main()
