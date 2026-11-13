"""Experience storage for the Gen 9 arena: deltas from collectors, an order-free merge, epoch snapshots.

Gen 9 design in progress (dave, task G9-D5). Used by no collector yet. The statistics and their
algebra are bridge_harness/experience.py (g9, interface I6); this module stores them without
knowing what any statistic means.

Collectors write one **envelope** per board and player:

  {'schema': 'experience-envelope-v1', 'delta': <experience-delta-v1>, 'source': collector or cohort,
   'completed_epoch': seconds, 'occasion': what situation this was, or None, 'epoch': arena epoch or None}

The delta itself is unchanged. The envelope carries what the merge needs to apply the arena's
counting rules: the completion time (for the snapshot cut-off and "earliest wins") and the
occasion, `occasion(family, seats, auction)`: the same deal, with the player in the same seats
after the same auction. A player plays every deal twice on one board (once in each room, in the
other seats), and a native auction that differs from the common one is a third table; those are
different occasions. The same occasion in a later cohort is a replay (a deal played again, as in
the Gen 7.1 rollout) and counts once. Envelopes are JSON lines, one file per collector and cohort,
appended as boards finish.

**Merge** (`merge`): every envelope from every source, in any order, gives the same stores, to the
bit: deltas are folded per player in a canonical order (completion time, then key). Rules:

- the same (player, key) twice with the same delta: a repeat publication, counted once, reported;
- the same (player, key) twice with different deltas: a conflict, refused (`ValueError`);
- the same (player, occasion) under two keys: the earlier completion counts, the later is dropped and
  reported;
- envelopes completed after the cut-off are left out and counted.

**Snapshot** (`epoch_snapshot`, `write_snapshot`, `load_snapshot`): the merged stores at an epoch
boundary, without the lists of applied keys, named by the sha256 of their canonical JSON. The name
is written into each player's snapshot (`snapshot` field of experience-v1) and goes into the epoch
manifest and every cohort manifest played under it. A snapshot file is written once; writing
different content under the same name is refused, and loading checks the name against the content.
"""
from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

from . import experience as xp

ENVELOPE = 'experience-envelope-v1'
SNAPSHOT = 'experience-epoch-snapshot-v1'


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False)


def occasion(family, seats, auction):
    """The situation a delta comes from: the deal family, the seats the player held ('NS', 'EW', or 'NESW' for a
    bidder that made every call of a common auction) and the auction (a list of calls)."""
    text = canonical([str(family), str(seats), [str(c) for c in auction]])
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def envelope(delta, source, completed_epoch, occasion=None, epoch=None):
    if delta.get('schema') != xp.DELTA_SCHEMA:
        raise ValueError('an envelope holds an experience-delta-v1')
    for s in delta['stats'].values():
        xp.check_stat(s)
    return dict(schema=ENVELOPE, delta=delta, source=str(source), completed_epoch=float(completed_epoch),
                occasion=None if occasion is None else str(occasion), epoch=epoch)


def write(path, envelopes):
    """Append envelopes to a JSON-lines file (gzip if the name ends in .gz)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'at') as f:
        for e in envelopes:
            if e.get('schema') != ENVELOPE:
                raise ValueError('not an experience envelope')
            f.write(canonical(e) + '\n')


def read(paths):
    out = []
    for path in paths:
        path = Path(path)
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt') as f:
            for n, line in enumerate(f, 1):
                if line.strip():
                    e = json.loads(line)
                    if e.get('schema') != ENVELOPE:
                        raise ValueError(f'{path}:{n}: not an experience envelope')
                    out.append(e)
    return out


def merge(envelopes, cut_off=None):
    """{player: experience-v1 store} and a report, the same for any order of the envelopes."""
    report = dict(envelopes=0, counted=0, repeats=0, occasion_repeats=[], after_cut_off=0, sources={})
    by_key = {}
    for e in envelopes:
        report['envelopes'] += 1
        if cut_off is not None and e['completed_epoch'] > cut_off:
            report['after_cut_off'] += 1
            continue
        d = e['delta']
        k = (d['player'], d['key'])
        if k in by_key:
            old = by_key[k]
            if canonical(old['delta']) != canonical(d):
                raise ValueError(f'two different deltas for player {k[0]!r} on {k[1]!r}')
            report['repeats'] += 1
            if (e['completed_epoch'], e['source']) < (old['completed_epoch'], old['source']):
                by_key[k] = e
            continue
        by_key[k] = e
    order = sorted(by_key.values(), key=lambda e: (e['delta']['player'], e['completed_epoch'], e['delta']['key']))
    seen, kept = {}, {}
    for e in order:
        d = e['delta']
        occ = e.get('occasion')
        if occ is not None:
            ok = (d['player'], occ)
            if ok in seen:
                report['occasion_repeats'].append(dict(player=d['player'], occasion=occ, kept=seen[ok], dropped=d['key']))
                continue
            seen[ok] = d['key']
        kept.setdefault(d['player'], []).append(e)
    stores = {}
    for player, items in kept.items():
        items.sort(key=lambda e: e['delta']['key'])       # the fold order is the key order: independent of input order
        stats = {}
        for e in items:
            stats = xp.merge_stats(stats, e['delta']['stats'])
            report['sources'][e['source']] = report['sources'].get(e['source'], 0) + 1
        stores[player] = dict(schema=xp.SCHEMA, player=player, boards=len(items), stats=stats,
                              applied=sorted(e['delta']['key'] for e in items))
        report['counted'] += len(items)
    report['sources'] = dict(sorted(report['sources'].items()))
    return dict(sorted(stores.items())), report


def _body(stores, epoch, cut_off, previous=None):
    players = {p: dict(schema=xp.SCHEMA, player=p, boards=s['boards'], stats=deepcopy(s['stats'])) for p, s in sorted(stores.items())}
    return dict(schema=SNAPSHOT, epoch=epoch, cut_off=cut_off, previous=previous, players=players)


def snapshot_id(body):
    return hashlib.sha256(canonical(body).encode()).hexdigest()


def epoch_snapshot(stores, epoch, cut_off, previous=None):
    """The frozen statistics of every player at an epoch boundary, named by their content."""
    body = _body(stores, epoch, cut_off, previous)
    sid = snapshot_id(body)
    doc = deepcopy(body)
    doc['id'] = sid
    for p in doc['players'].values():
        p['snapshot'] = sid
    return doc


def _strip(doc):
    body = {k: deepcopy(v) for k, v in doc.items() if k != 'id'}
    for p in body['players'].values():
        p.pop('snapshot', None)
    return body


def verify(doc):
    if doc.get('schema') != SNAPSHOT:
        raise ValueError('not an experience epoch snapshot')
    if snapshot_id(_strip(doc)) != doc.get('id'):
        raise ValueError('snapshot content does not match its name')
    for p in doc['players'].values():
        if p.get('snapshot') != doc['id'] or 'applied' in p:
            raise ValueError('a player snapshot must carry the epoch snapshot name and no applied keys')
        xp.check(p)
    return doc


def write_snapshot(folder, doc):
    """Write once: <folder>/<id>.json.gz. The same content again is a no-op; other content under the name is refused."""
    verify(doc)
    path = Path(folder) / f"{doc['id']}.json.gz"
    if path.exists():
        if canonical(load_snapshot(path)) != canonical(doc):
            raise ValueError(f'{path} exists with other content')
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as f:   # no time in the header: same content, same bytes
        f.write(canonical(doc).encode())
    tmp.replace(path)
    return path


def load_snapshot(path):
    with gzip.open(path, 'rt') as f:
        doc = json.load(f)
    verify(doc)
    if Path(path).name != f"{doc['id']}.json.gz":
        raise ValueError(f'{path} is not named by its content')
    return doc


def player_snapshot(doc, player):
    """The experience-v1 snapshot a PlayerModel carries for this player: empty (but named) for a player the
    snapshot has never seen, so a newcomer is read as its profile."""
    p = doc['players'].get(player)
    if p is None:
        return dict(schema=xp.SCHEMA, player=str(player), boards=0, stats={}, snapshot=doc['id'])
    return deepcopy(p)
