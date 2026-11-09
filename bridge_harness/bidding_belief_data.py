"""Recover supervised auction beliefs from committed DDS-bidding training batches.

No bidder inference, DDS call, or play rollout is needed. The legacy v1 batches
omit the cards, so we reproduce them from the pinned generator and verify EVERY
canonical deal ID before attaching labels. Bidding dev/confirmation is excluded.
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np

from . import bidding_env
from .auction_belief import MAX_CALLS, SCHEMA, encode_auction
from .bidding_env import deal_key, deal_split, make_board
from .core import auction_contract
from .selfplay import atomic_json
from .training import digest


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def belief_split(family):
    """Independent, stable split; both rooms, all prefixes/rotations stay together."""
    n = int(hashlib.sha256(('bidding-belief-v1:' + family).encode()).hexdigest()[:8], 16) % 100
    return 'train' if n < 80 else 'validation' if n < 90 else 'test'


def overlaps(hands, reserved):
    return any(digest(hands[i:] + hands[:i]) in reserved for i in range(4))


def examples(board, calls, family):
    """One pre-call and one complete-auction view per seat; no future input."""
    truth = np.empty(52, np.int8)
    for seat, hand in enumerate(board.hands):
        truth[list(hand)] = seat
    for observer in range(4):
        turns = [i for i in range(len(calls)) if (board.dealer + i) % 4 == observer]
        # A fixed deal/observer hash keeps room selection and repeated exports stable.
        pick = int(hashlib.sha256(f'{family}:{observer}'.encode()).hexdigest()[:8], 16)
        before = turns[pick % len(turns)]
        for length, kind in ((before, 0), (len(calls), 1)):
            x, support = encode_auction(board.hands[observer], observer, board.dealer,
                                        board.vulnerability, calls[:length])
            y = (truth - observer) % 4
            if not support[np.arange(52), y].all():
                raise ValueError('Label outside legal ownership support')
            yield dict(**x, owner_target=y, owner_loss_mask=y != 0,
                       split_group=family, kind=kind)


def committed_batches(root, manifest, state):
    """Read only batches covered by the captured committed state; fail on gaps."""
    current = int(state['attempt'])
    offsets = Counter()
    total = 0
    for path in sorted((root / 'batches').glob('a*-*/auctions.json')):
        attempt, offset = map(int, path.parent.name[1:].split('-'))
        if attempt > current or (attempt == current and offset >= state['trained_pairs']):
            continue
        if offset != offsets[attempt]:
            raise ValueError(f'Missing/overlapping batch before {path}')
        raw = path.read_bytes()
        rows = json.loads(raw)
        metrics = json.loads((path.parent / 'metrics.json').read_text())
        if not rows or len(rows) != metrics['pairs']:
            raise ValueError(f'Batch count mismatch: {path}')
        if attempt == current and offset + len(rows) > state['trained_pairs']:
            raise ValueError('Batch crosses committed boundary')
        offsets[attempt] += len(rows)
        total += len(rows)
        yield path, hashlib.sha256(raw).hexdigest(), attempt, offset, rows
    if total != state['total_train_pairs']:
        raise ValueError(f'Expected {state["total_train_pairs"]} committed pairs, recovered {total}')


def export(root, legacy, out, exclude_groups=(), shard_rows=8192):
    root, legacy, out = map(Path, (root, legacy, out))
    if out.exists():
        raise ValueError('Refusing to overwrite a frozen dataset')
    if shard_rows < 8:
        raise ValueError('Shard size must be at least eight rows')
    manifest_raw = (root / 'manifest.json').read_bytes()
    state_raw = (root / 'state.json').read_bytes()
    manifest, state = json.loads(manifest_raw), json.loads(state_raw)
    if manifest['schema'] != 'dds-bidding-loop-v1':
        raise ValueError('Unsupported source schema')
    for name in ('bidding_env.py', 'core.py'):
        if sha(Path(bidding_env.__file__).with_name(name)) != manifest['source_sha256'][name]:
            raise ValueError(f'Deal reconstruction source differs: {name}')
    audit = json.loads((legacy / 'audit.json').read_text())
    if not audit['validated'] or audit['schema'] != SCHEMA:
        raise ValueError('Legacy auction dataset is not audited/compatible')
    reserved = set()
    legacy_files = {}
    # Test metadata only; test observations and labels are never selected here.
    for split in ('train', 'validation', 'test'):
        p = legacy / f'{split}.npz'
        if sha(p) != audit['exports'][split]:
            raise ValueError('Legacy export changed')
        with np.load(p, allow_pickle=False) as z:
            reserved.update(map(str, np.unique(z['split_group'])))
        if split != 'test':
            legacy_files[split] = dict(path=str(p.resolve()), sha256=sha(p))
    exclusions = []
    for p in map(Path, exclude_groups):
        reserved.update(json.loads(p.read_text())['deal_ids'])
        exclusions.append(dict(path=str(p.resolve()), sha256=sha(p)))
    out.mkdir(parents=True)
    buffers = {s: [] for s in ('train', 'validation')}
    shards = {s: [] for s in buffers}
    counts = Counter()
    groups = {s: set() for s in ('train', 'validation', 'test')}
    seen = set()
    sources = []

    def flush(split):
        rows = buffers[split]
        if not rows:
            return
        p = out / f'{split}-{len(shards[split]):04d}.npz'
        np.savez_compressed(p, **{k: np.stack([r[k] for r in rows]) for k in rows[0]})
        shards[split].append(dict(file=p.name, rows=len(rows), sha256=sha(p)))
        rows.clear()

    for path, file_sha, attempt, offset, rows in committed_batches(root, manifest, state):
        sources.append(dict(batch=path.parent.name, sha256=file_sha, pairs=len(rows)))
        seed = manifest['config']['seed'] + attempt * 100003
        for j, row in enumerate(rows):
            b = make_board(seed, offset+j, 'train')
            family = deal_key(b.hands, True)
            if family != row['deal_id'] or deal_split(b.hands) != 'train':
                raise ValueError(f'Deal reconstruction mismatch: {path}:{j}')
            counts['source_pairs'] += 1
            if family in seen:
                raise ValueError('Repeated underlying deal family in source')
            seen.add(family)
            if overlaps(b.hands, reserved):
                counts['reserved_pairs'] += 1
                continue
            split = belief_split(family)
            groups[split].add(family)
            if len(row['tables']) != 2:
                raise ValueError('Expected paired auctions')
            auctions = set()
            for room, table in enumerate(row['tables']):
                calls = tuple(table['calls'])
                c = auction_contract(b.dealer, calls)
                if table['contract'] != (c.text() if c else None) or table['declarer'] != (c.declarer if c else None):
                    raise ValueError('Stored contract/declarer differs from legal auction')
                counts['source_auctions'] += 1
                if calls in auctions:
                    counts['duplicate_room_auctions'] += 1
                    continue
                auctions.add(calls)
                if len(calls) > MAX_CALLS:
                    counts['overlength_auctions'] += 1
                    continue  # No truncation that could change auction meaning.
                counts[f'{split}_unique_auctions'] += 1
                if split == 'test':
                    continue  # Reserve families without exporting hidden labels.
                for e in examples(b, calls, family):
                    e.update(attempt=attempt, batch_offset=offset, room=room)
                    buffers[split].append(e)
                    counts[f'{split}_rows'] += 1
                if len(buffers[split]) >= shard_rows:
                    flush(split)
        if len(sources) % 50 == 0:
            print(json.dumps(dict(event='export', batches=len(sources), pairs=counts['source_pairs'])), flush=True)
    for s in buffers:
        flush(s)
        if not shards[s]:
            raise ValueError(f'No {s} data')
    for a in groups:
        for b in groups:
            if a != b and groups[a] & groups[b]:
                raise ValueError('Family split leakage')
    result = dict(schema=SCHEMA, validated=True, source_run=str(root.resolve()),
        source_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        source_state_sha256=hashlib.sha256(state_raw).hexdigest(),
        source_state=state, source_batches=sources, counts=dict(counts),
        splits={s: dict(deals=len(g), rows=counts[f'{s}_rows']) for s,g in groups.items()},
        shards=shards, legacy=legacy_files, exclusions=exclusions,
        reserved_original_ids=len(reserved), additional_dds_calls=0, additional_play_games=0,
        bidding_evaluation_imported=False, belief_test_exported=False,
        split_note='Belief validation/test are reserved bidding TRAIN families; not an independent end-to-end bidding test.',
        behavior='Sampled learner plus greedy frozen league; legacy replay is greedy BEN.',
        identity_note='Batch offset identifies learner collection snapshot. Legacy source omits exact per-board opponent version; never invent it.')
    atomic_json(out / 'dataset.json', result)
    atomic_json(out / 'reserved-families.json', {s: sorted(g) for s,g in groups.items()})
    return result
