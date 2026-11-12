"""Read-only pooled arena gate for the authorized Gen7.1 comparison.

Only this producer is stopped. No peer, model, or closed selfplay plan is modified.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import time

from phase1_fleet import fetch_bytes

PAIR = '71s-32~7s-32'
ALLOWED_OTHERS = {'7s-32', '6-32', 'ben64', 'ben'}
TRAINING_SHA256 = '4818856d731bee23ea38cf16b478a73106ad06a2116dca046fae8a9098b103e3'


def orientation(pair):
    if pair == PAIR:
        return 1
    if pair == '7s-32~71s-32':
        return -1
    return 0


def observation(row, cohort):
    sign = orientation(row['pair'])
    if not sign:
        return None
    # Common bidding only. Native results are a separate condition, never extra boards.
    value = row['imps']
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Comparison record lacks finite played common-bidding IMPs')
    if row.get('own_imps', value) != value:
        raise ValueError('Canonical Gen7.1/Gen7.0 pair has different common/native results')
    if not isinstance(row['family'], str) or not row['family']:
        raise ValueError('Comparison record lacks deal family')
    return dict(cohort=cohort, index=int(row['index']), family=row['family'],
                completed_epoch=float(row['completed_epoch']), imps=sign * value,
                episode_sha256=row['episode_sha256'])


def deduplicate(rows):
    """Keep earliest completion per family, using identity/index for outcome-blind ties."""
    by_record = {}
    for row in rows:
        key = (row['cohort'], row['index'])
        if key in by_record and by_record[key] != row:
            raise ValueError('Conflicting published/local record: ' + repr(key))
        by_record[key] = row
    families = {}
    for row in sorted(by_record.values(), key=lambda r: (r['completed_epoch'], r['cohort'], r['index'])):
        families.setdefault(row['family'], row)
    return sorted(families.values(), key=lambda r: (r['completed_epoch'], r['cohort'], r['index']))


def statistics_for(rows):
    values = [r['imps'] for r in rows]
    n = len(values)
    mean = statistics.mean(values) if n else None
    ci = None
    if n >= 2:
        from scipy.stats import t
        half = float(t.ppf(.975, n - 1)) * statistics.stdev(values) / math.sqrt(n)
        ci = [mean - half, mean + half]
    return dict(boards=n, mean_imps=mean, ci95=ci,
                minimum_boards_met=n >= 1000,
                positive_lower_bound=bool(ci and ci[0] > 0),
                qualified=bool(n >= 1000 and ci and ci[0] > 0))


def registered_heads(registry, heads):
    """Use only registered arena cohorts, honoring each retired source's pinned revision."""
    selected = []
    for source in registry['sources']:
        branch = source['branch']
        if not (source.get('group') == 'gen7' or str(source.get('generation', '')).startswith('7')):
            continue
        if not branch.startswith(('arena-gen7-', 'arena-gen71-')) or any(x in branch for x in ('pre7', 'trial', 'test', 'prototype')):
            continue
        revision = source.get('revision') or heads.get(branch)
        if not revision or not re.fullmatch('[0-9a-f]{40}', revision):
            raise ValueError('Registered arena source lacks an available pinned revision: ' + branch)
        selected.append((branch, revision, source['cohort']))
    return selected


def exclusion_list(run, manifest):
    declared = manifest.get('evaluation_exclusions')
    path = run / (declared['path'] if declared else 'evaluation-exclusions.json')
    raw = path.read_bytes()
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != TRAINING_SHA256 or declared and declared['sha256'] != checksum:
        raise ValueError('Training-family exclusion checksum mismatch')
    values = json.loads(raw)
    if not isinstance(values, list) or any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v) for v in values):
        raise ValueError('Invalid training-family exclusion list')
    if not declared:
        # Existing immutable cohorts may supply a full-corpus disjointness proof rather
        # than rewrite their manifest. New preparations use --exclude-families.
        audit = json.loads((run / 'evaluation-exclusion-audit.json').read_text())
        if (audit['manifest'] != manifest['identity'] or audit['corpus_sha256'] != manifest['corpus_sha256']
                or audit['training_list_sha256'] != checksum or audit['corpus_training_overlap'] != 0
                or audit['distinct_corpus_families'] != manifest['target']):
            raise ValueError('Existing cohort lacks a matching full-corpus exclusion proof')
    return set(values), dict(path=str(path.relative_to(run)), sha256=checksum, families=len(set(values)))


def eligible_rows(rows, trained):
    excluded = {r['family'] for r in rows if r['family'] in trained}
    return deduplicate([r for r in rows if r['family'] not in trained]), excluded


def fetch_snapshot(item, actors):
    branch, revision = item
    manifest = json.loads(fetch_bytes(revision, 'arena/manifest.json'))
    bots = manifest.get('bots', {})
    if any(bots.get(k, {}).get('identity') != v for k, v in actors.items()):
        return dict(branch=branch, revision=revision, excluded='different-actors')
    plan = json.loads(fetch_bytes(revision, 'recovery/plan.json'))
    if not plan.get('launch_enabled') or plan.get('pending') or plan.get('campaign') != manifest.get('campaign'):
        return dict(branch=branch, revision=revision, excluded='not-published-ready-plan')
    if plan.get('pair_weights') != manifest.get('pair_weights') or plan.get('common_bidder') != '6-32':
        raise ValueError('Plan/manifest mismatch: ' + branch)
    for pair in plan['pair_weights']:
        parts = pair.split('~')
        if len(parts) != 2 or parts.count('71s-32') != 1 or next(p for p in parts if p != '71s-32') not in ALLOWED_OTHERS:
            return dict(branch=branch, revision=revision, excluded='not-authorized-comparison-plan')
    if not any(orientation(p) for p in plan['pair_weights']):
        return dict(branch=branch, revision=revision, excluded='no-71-vs-70-pair')
    data = json.loads(fetch_bytes(revision, 'arena/data.json'))
    if data['manifest_identity'] != manifest['identity']:
        raise ValueError('Snapshot manifest mismatch: ' + branch)
    prefix = 'arena/replays/data/' + manifest['identity'] + '/'
    index = json.loads(fetch_bytes(revision, prefix + 'index.json'))
    if index['cohort'] != manifest['identity']:
        raise ValueError('Replay cohort mismatch: ' + branch)
    records = list(index.get('records', []))
    for name in index.get('record_shards', []):
        if Path(name).name != name or not name.endswith('.json'):
            raise ValueError('Invalid shard name')
        content = fetch_bytes(revision, prefix + name)
        if hashlib.sha256(content).hexdigest() != index['record_shard_sha256'][name]:
            raise ValueError('Replay shard checksum mismatch: ' + branch)
        records.extend(json.loads(content))
    rows = []
    for row in records:
        if row['completed_epoch'] <= data['generated_epoch'] and orientation(row['pair']):
            rows.append(observation(row, manifest['identity']))
    return dict(branch=branch, revision=revision, cohort=manifest['identity'], rows=rows)


def fetch_registered_snapshot(item, actors):
    branch, revision, cohort = item
    result = fetch_snapshot((branch, revision), actors)
    if result.get('cohort') and result['cohort'] != cohort:
        raise ValueError('Registered cohort/manifest mismatch: ' + branch)
    return result


def update(run, runtime):
    run, runtime = Path(run), Path(runtime)
    m = json.loads((run / 'manifest.json').read_text())
    actors = {k: m['bots'][k]['identity'] for k in ('71s-32', '7s-32')}
    inventory_path = run / 'gen71-gate-inventory.json'
    previous = json.loads(inventory_path.read_text()) if inventory_path.exists() else {}
    if previous and previous['actors'] != actors:
        raise ValueError('Inventory belongs to different actors')
    trained, exclusion = exclusion_list(run, m)
    # Rebuild eligibility from the current pinned registry. A previously counted
    # unregistered or training-family row must never survive by monotone union.
    rows = []
    output = subprocess.check_output(['git', '-C', str(runtime), 'ls-remote', '--heads',
        'origin', 'gh-pages', 'arena-gen7*'], text=True, timeout=40)
    heads = {l.split()[1].removeprefix('refs/heads/'):l.split()[0] for l in output.splitlines() if l.strip()}
    registry_revision = heads['gh-pages']
    registry = json.loads(fetch_bytes(registry_revision, 'arena/gen6-sources.json'))
    selected = registered_heads(registry, heads)
    if not any(s[2] == m['identity'] for s in selected):
        raise ValueError('This cohort is not registered for the arena gate')
    snapshots, errors = [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [(item[0], pool.submit(fetch_registered_snapshot, item, actors)) for item in selected]
        for branch, future in futures:
            try:
                result = future.result()
                rows.extend(result.get('rows', []))
                snapshots.append({k: v for k, v in result.items() if k != 'rows'})
            except Exception as exc:
                errors.append(dict(branch=branch, error=repr(exc)))
    for path in (run / 'receipts').glob('*.json'):
        receipt = json.loads(path.read_text())
        if receipt['manifest_identity'] != m['identity']:
            raise ValueError('Local receipt identity mismatch')
        row = observation(receipt, m['identity'])
        if row is not None:
            rows.append(row)
    unique, excluded_training = eligible_rows(rows, trained)
    from bridge_harness.selfplay import atomic_json
    atomic_json(inventory_path, dict(schema='gen71-eligible-gate-v2', actors=actors, rows=unique,
                                    registry_revision=registry_revision, training_exclusions=exclusion))
    result = dict(epoch=time.time(), status='partial' if errors else 'checked', actors=actors,
        pair=PAIR, condition='common', metric='played IMPs per board for 71s-32',
        **statistics_for(unique), snapshots=snapshots, errors=errors,
        registry_revision=registry_revision, training_exclusions=exclusion,
        excluded_training_families=len(excluded_training),
        selfplay_launch_enabled=False,
        method='Current registered, revision-pinned arena records plus this registered producer\'s local atomic receipts; '
               'published v4.1 training families excluded; eligibility rebuilt on every check; '
               'exact actors, ready published plan, '
               'checksum and snapshot cutoff checked; one earliest completion per family; '
               'two-sided Student-t 95% CI. Descriptive interval, unadjusted for repeated monitoring. '
               'External research tests and native duplicate rooms excluded. A published opening is required before selfplay.')
    result['qualified'] = bool(result['qualified'] and not errors)
    atomic_json(run / 'gen71-gate-progress.json', result)
    if result['qualified'] and not errors:
        stop = run / 'STOP'
        if not stop.exists():
            stop.write_text('Gen7.1 pooled comparison gate met; drain, preserve records, await published selfplay opening and a new identity.\n')
        atomic_json(run / 'gen71-gate-stop.json', result)
    return result
