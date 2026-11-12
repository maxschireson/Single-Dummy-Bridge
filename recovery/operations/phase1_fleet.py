"""Read published Gen7 phase-1 records and stop this producer at shared limits."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

REPO = 'maxschireson/Single-Dummy-Bridge'
PAIRS = ('7s-32~6-32', '7s-32~ben64', '7s-32~ben', '7s-32~5RZ32', '7s-32~1')


def canonical_pair(value):
    parts = value.split('~')
    if len(parts) != 2 or parts.count('7s-32') != 1:
        return None
    other = next(p for p in parts if p != '7s-32')
    pair = '7s-32~' + other
    return pair if pair in PAIRS else None


def count_families(rows):
    seen = {p: set() for p in PAIRS}
    for row in rows:
        pair = canonical_pair(row['pair'])
        if pair and isinstance(row.get('family'), str) and row['family']:
            seen[pair].add(row['family'])
    return seen


def fetch_bytes(revision, path):
    url = f'https://raw.githubusercontent.com/{REPO}/{revision}/{path}'
    with urllib.request.urlopen(url, timeout=20) as response:
        return response.read()


def fetch_snapshot(item, actor_identity):
    branch, revision = item
    manifest = json.loads(fetch_bytes(revision, 'arena/manifest.json'))
    if manifest.get('campaign') != 'gen7-phase1-20261112':
        return dict(branch=branch, revision=revision, excluded='not-phase1')
    if manifest.get('bots', {}).get('7s-32', {}).get('identity') != actor_identity:
        return dict(branch=branch, revision=revision, excluded='different-actor-configuration')
    data = json.loads(fetch_bytes(revision, 'arena/data.json'))
    if data['manifest_identity'] != manifest['identity']:
        raise ValueError('Snapshot manifest mismatch: ' + branch)
    prefix = f"arena/replays/data/{manifest['identity']}/"
    index = json.loads(fetch_bytes(revision, prefix + 'index.json'))
    if index['cohort'] != manifest['identity']:
        raise ValueError('Snapshot replay identity mismatch: ' + branch)
    rows = list(index.get('records', []))
    for name in index.get('record_shards', []):
        if Path(name).name != name or not name.endswith('.json'):
            raise ValueError('Invalid replay shard name')
        content = fetch_bytes(revision, prefix + name)
        if hashlib.sha256(content).hexdigest() != index['record_shard_sha256'][name]:
            raise ValueError('Replay shard checksum mismatch: ' + branch)
        rows.extend(json.loads(content))
    rows = [dict(pair=r['pair'], family=r['family']) for r in rows
            if r['completed_epoch'] <= data['generated_epoch'] and canonical_pair(r['pair'])]
    return dict(branch=branch, revision=revision, cohort=manifest['identity'], rows=rows)


def update(run, runtime):
    """Counts are monotone, deduplicated by family/pair, and independent of scores."""
    run, runtime = Path(run), Path(runtime)
    m = json.loads((run / 'manifest.json').read_text())
    actor = m['bots']['7s-32']['identity']
    inventory_path = run / 'phase1-seen-families.json'
    previous = json.loads(inventory_path.read_text()) if inventory_path.exists() else {}
    if previous and previous['actor_identity'] != actor:
        raise ValueError('Fleet inventory belongs to a different Gen7 actor')
    seen = {pair: set(previous.get('families', {}).get(pair, [])) for pair in PAIRS}
    output = subprocess.check_output(['git', '-C', str(runtime), 'ls-remote', '--heads',
        'origin', 'arena-gen7*'], text=True, timeout=40)
    heads = [(line.split()[1].removeprefix('refs/heads/'), line.split()[0])
             for line in output.splitlines() if line.strip()]
    snapshots = []; errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [(branch, pool.submit(fetch_snapshot, (branch, revision), actor)) for branch, revision in heads]
        for branch, future in futures:
            try:
                snapshot = future.result()
                for pair, families in count_families(snapshot.get('rows', [])).items():
                    seen[pair].update(families)
                snapshots.append({k:v for k,v in snapshot.items() if k != 'rows'})
            except Exception as exc:
                errors.append(dict(branch=branch, error=repr(exc)))
    # Include local committed receipts, avoiding a publication-delay overshoot.
    local_rows = []
    for path in (run / 'receipts').glob('*.json'):
        row = json.loads(path.read_text())
        if row['manifest_identity'] != m['identity']:
            raise ValueError('Local receipt identity mismatch')
        local_rows.append(row)
    for pair, families in count_families(local_rows).items():
        seen[pair].update(families)
    from bridge_harness.selfplay import atomic_json
    atomic_json(inventory_path, dict(actor_identity=actor, families={p:sorted(v) for p,v in seen.items()}))
    counts = {p:len(v) for p,v in seen.items()}
    owned_complete = all(counts[p] >= 2000 for p in m['phase1']['owned_pairs'])
    all_complete = all(v >= 2000 for v in counts.values())
    status = dict(epoch=time.time(), status='partial' if errors else 'checked',
        actor_identity=actor, counts=counts, target_per_pair=2000, owned_complete=owned_complete,
        all_five_complete=all_complete, phase2_authorized=False, snapshots=snapshots, errors=errors,
        method='Published authorized phase1 feeds plus local committed receipts; canonical actor identity; '
               'deduplicated by pair and deal family, independent of outcomes. Only published peers are observable.')
    atomic_json(run / 'phase1-global-progress.json', status)
    if owned_complete or all_complete:
        stop = run / 'STOP'
        if not stop.exists():
            stop.write_text('Gen7 phase1 shared non-BEN pair targets reached; drain and await instructions. Phase2 remains closed.\n')
        atomic_json(run / 'phase1-stop.json', status)
    return status
