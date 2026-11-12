"""The arena as a population: player packages, registry log, epochs and the boundary controller.

Gen 9 design in progress (dave, task G9-D4; design: docs/gen9/arena.md; statistics:
docs/gen9/arena-statistics.md and bridge_harness/arena_ratings.py). Used by no collector.

Everything a collector needs is in the current epoch manifest; everything that changes the arena
is an event in the registry log; the next epoch is a function of the previous one, the log and
the results. A control directory has the layout the control branch will have:

  registry.jsonl            append-only events (submit, activate, open-test, promote, demote, retire, protect, ...)
  queue/*.json              events written by people, applied (and moved into the log) at the next boundary
  epochs/<nnnn>.json        epoch-v1 manifests, never edited
  CURRENT                   the number of the epoch collectors play
  ratings/<nnnn>-<cond>.json ratings-v1 at the close of an epoch
  snapshots/<id>.json.gz    experience snapshots (bridge_harness/experience_store.py)
  results/e<nnnn>/<slot>.jsonl  one row per board, written by collectors

Player packages (player-package-v1) live in source under configs/players/ and are immutable.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import time

import numpy as np

from . import arena_ratings as ar
from . import experience_store as xs

PACKAGE = 'player-package-v1'
EPOCH = 'epoch-v1'
RULES = 'arena-rules-v1'
KINDS = ('house', 'anchor', 'synthetic', 'outside', 'guest')
EVENTS = ('submit', 'activate', 'open-test', 'promote', 'demote', 'retire', 'protect', 'unprotect', 'champion')
STATUSES = ('candidate', 'active', 'anchor', 'champion', 'retired')
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,47}')
PATH_KEYS = ('bidding', 'belief', 'policy', 'lead_belief', 'scorer', 'system_scorer', 'gen7_policy', 'url', 'config')


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


# ---- packages --------------------------------------------------------------------------------

def _has_key(obj, key):
    if isinstance(obj, dict):
        return key in obj or any(_has_key(v, key) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_key(v, key) for v in obj)
    return False


def check_package(p):
    """Admission checks that need no machine: form, kind, licence, lineage declared, no oracle anywhere."""
    problems = []
    if p.get('schema') != PACKAGE:
        problems.append('schema is not player-package-v1')
    if not isinstance(p.get('id'), str) or not _ID.fullmatch(p['id']) or '~' in p['id']:
        problems.append('id must be 1-48 letters, digits, dot, dash or underscore')
    if p.get('kind') not in KINDS:
        problems.append(f'kind must be one of {KINDS}')
    if not isinstance(p.get('bundle'), dict):
        problems.append('bundle missing')
    if 'lineage' not in p or 'training_families' not in (p.get('lineage') or {}):
        problems.append('lineage.training_families must be declared (an empty object for a bot with no trained nets)')
    if p.get('licence') != 'redistributable':
        problems.append('licence must be redistributable')
    if _has_key(p, 'oracle'):
        problems.append('an oracle bot (given the deal) may not be rostered')
    return problems


def identity(package, artifact_sha256=None):
    """The player's identity: its bundle with every artifact path left out, the artifacts' sha256 (the bundle's own
    `artifact_sha256` and any given here), and its declaration. The same nets under another folder are the same player."""
    bundle = deepcopy(package['bundle'])
    artifacts = dict(bundle.pop('artifact_sha256', None) or {}, **(artifact_sha256 or {}))
    def strip(d):
        if isinstance(d, dict):
            return {k: ('<artifact>' if k in PATH_KEYS and isinstance(v, str) else strip(v)) for k, v in d.items()}
        if isinstance(d, list):
            return [strip(v) for v in d]
        return d
    return sha(dict(bundle=strip(bundle), artifacts=artifacts, declaration=package.get('declaration')))


def load_packages(folder):
    out = {}
    for path in sorted(Path(folder).glob('*.json')):
        p = json.loads(path.read_text())
        if p.get('schema') == PACKAGE:
            out[p['id']] = p
    return out


# ---- registry log --------------------------------------------------------------------------

def event(name, player, author, authority, **extra):
    if name not in EVENTS:
        raise ValueError(f'unknown event {name}')
    return dict(event=name, player=player, author=author, authority=authority, **extra)


def read_log(control):
    path = Path(control) / 'registry.jsonl'
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()] if path.exists() else []


def append_log(control, events, t=None):
    path = Path(control) / 'registry.jsonl'
    n = len(read_log(control))
    with path.open('a') as f:
        for k, e in enumerate(events):
            f.write(canonical(dict(e, seq=n + k, t=t or time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))) + '\n')


def fold(log):
    """Status of every player from the log: candidate on submit (anchor for kind anchor), then the events."""
    st = {}
    for e in sorted(log, key=lambda e: e['seq']):
        p, k = e['player'], e['event']
        s = st.setdefault(p, dict(status=None, protected=False, package_sha256=None, kind=None, test=None, since=None, model=None))
        if k == 'submit':
            s.update(status='anchor' if e.get('kind') == 'anchor' else 'candidate', package_sha256=e['package_sha256'],
                     kind=e.get('kind'), since=e.get('epoch'), protected=e.get('kind') == 'anchor', model=e.get('model'))
        elif k == 'activate':
            s['status'] = 'active' if s['status'] == 'candidate' else s['status']
            s['since'] = e.get('epoch')
        elif k == 'champion':
            for q in st.values():
                if q['status'] == 'champion':
                    q['status'] = 'anchor' if q['protected'] else 'active'
            s['status'] = 'champion'; s['test'] = None
        elif k == 'open-test':
            s['test'] = dict(champion=e['champion'], opened_epoch=e['epoch'])
        elif k == 'promote':
            for q in st.values():
                if q['status'] == 'champion':
                    q['status'] = 'anchor' if q['protected'] else 'active'
            s['status'] = 'champion'; s['test'] = None
        elif k == 'demote':
            s['test'] = None
        elif k == 'retire':
            s['status'] = 'retired'; s['test'] = None
        elif k == 'protect':
            s['protected'] = True
        elif k == 'unprotect':
            s['protected'] = False
    return st


def champion_of(st):
    ch = [p for p, s in st.items() if s['status'] == 'champion']
    if len(ch) != 1:
        raise ValueError(f'the registry needs exactly one champion, has {ch}')
    return ch[0]


# ---- schedule ---------------------------------------------------------------------------------

def pair_name(a, b):
    return f'{a}~{b}'


def schedule(st, rules, previous=None):
    """Purposes and integer pair weights for the next epoch (docs/gen9/arena.md section 4). `previous` is the last
    epoch's schedule: a pair that keeps its purpose may not more than double or halve its weight; a pair whose purpose
    changed (an admission becoming a promotion test, say) or that is new takes its weight at once."""
    champ = champion_of(st)
    anchors = sorted(p for p, s in st.items() if s['status'] == 'anchor')
    actives = sorted(p for p, s in st.items() if s['status'] == 'active')
    candidates = sorted(p for p, s in st.items() if s['status'] == 'candidate')
    testing = sorted(p for p, s in st.items() if s['test'] and s['status'] != 'retired')
    purposes = {
        'promotion': [pair_name(p, champ) for p in testing],
        'admission': [pair_name(p, q) for p in candidates for q in [champ, *anchors[:2]]],
        'panel': [pair_name(champ, a) for a in anchors],
        'training': [pair_name(champ, champ)] + [pair_name(champ, a) for a in actives if a not in testing],
    }
    shares = dict(rules['shares'])
    spare = sum(shares[k] for k, v in purposes.items() if not v and k != 'training')
    shares['training'] += spare
    units = rules.get('weight_units', 100)
    weights = {}
    for purpose, pairs in purposes.items():
        if not pairs or shares.get(purpose, 0) <= 0:
            continue
        w = max(1, round(shares[purpose] * units / len(pairs)))
        for p in pairs:
            weights[p] = weights.get(p, 0) + w
    if previous:
        ratio = rules.get('max_weight_ratio', 2)
        was = {p: k for k, ps in previous.get('purposes', {}).items() for p in ps}
        now = {p: k for k, ps in purposes.items() for p in ps}
        for p, w in weights.items():
            old = previous['pair_weights'].get(p)
            if old and was.get(p) == now.get(p):
                weights[p] = int(min(max(w, math.ceil(old / ratio)), old * ratio))
    return dict(purposes={k: v for k, v in purposes.items() if v}, pair_weights=dict(sorted(weights.items())), floors=floors(st, rules))


def floors(st, rules):
    """The rules' fixed floors whose players are all in the arena: groups of pairs that play the same deals, n boards
    each, every epoch (a comparison such as the Gen 9 bot and its control against one guest). The scheduler places
    the rest of an epoch's boards."""
    out = []
    for f in rules.get('floors', []):
        players = {x for p in f['pairs'] for x in p.split('~')}
        if all((st.get(x) or {}).get('status') not in (None, 'retired') for x in players):
            out.append(dict(pairs=list(f['pairs']), boards=int(f['boards']), same_deals=bool(f.get('same_deals', True)),
                            purpose=f.get('purpose', 'comparison')))
    return out


def pair_at(seed, slot, k, weights):
    """The pair of board k of a slot: blocks of the repeated weight list, each shuffled by its own stream."""
    block = [p for p, w in sorted(weights.items()) for _ in range(w)]
    rng = np.random.default_rng([seed, slot, k // len(block)])
    order = rng.permutation(len(block))
    return block[order[k % len(block)]]


def deal_index(slot, k):
    return slot * (1 << 20) + k


# k of a floor board: above the scheduler's boards, by floor group, pair and board; pairs of a same-deals group share
# the deal index of board j
FLOOR_BASE, FLOOR_GROUP, FLOOR_PAIR = 1 << 19, 1 << 15, 1 << 11


# ---- epochs ---------------------------------------------------------------------------------

def epoch_boards(rules, n):
    """Boards in epoch n: the rules' epoch size, or its `first` size for epoch 1."""
    e = rules['epoch']
    return int(e.get('first', e['boards'])) if n == 1 else int(e['boards'])


def epoch_path(control, n):
    return Path(control) / 'epochs' / f'{n:04d}.json'


def current(control):
    n = int((Path(control) / 'CURRENT').read_text().strip())
    m = json.loads(epoch_path(control, n).read_text())
    if m['id'] != epoch_id(m):
        raise ValueError(f'epoch {n} does not match its id')
    return m


def epoch_id(m):
    return sha({k: v for k, v in m.items() if k not in ('id', 'opened_utc')})


def make_epoch(n, previous, st, packages, rules, snapshot_id, applied, source_commit=None):
    sch = schedule(st, rules, previous['schedule'] if previous else None)
    rostered = sorted({x for p in sch['pair_weights'] for x in p.split('~')} | {x for f in sch['floors'] for p in f['pairs'] for x in p.split('~')})
    players = {p: dict(package_sha256=st[p]['package_sha256'], identity=identity(packages[p]), status=st[p]['status'],
                       protected=st[p]['protected'], test=st[p]['test'], model=st[p].get('model')) for p in rostered}
    if sum(f['boards'] * len(f['pairs']) for f in sch['floors']) > epoch_boards(rules, n):
        raise ValueError('the floors need more boards than an epoch has')
    excluded = sorted({f for p in rostered for f in (packages[p].get('lineage') or {}).get('training_families', {}).values()})
    m = dict(schema=EPOCH, epoch=n, previous=previous['id'] if previous else None, rules=dict(version=rules['version'], sha256=sha(rules)),
             source_commit=source_commit, champion=champion_of(st), players=players, schedule=sch,
             conditions=dict(regimes=['common', 'native'], common_bidder=rules.get('common_bidder')),
             deals=dict(generator='gen8_match.deal(seed, slot * 2**20 + k)', seed=None, exclude_training_family_lists=excluded),
             experience_snapshot=snapshot_id, end=dict(boards=epoch_boards(rules, n)), events_applied=applied)
    m['deals']['seed'] = int(sha(dict(m, deals=None))[:8], 16)
    m['id'] = epoch_id(m)
    m['opened_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    return m


def write_epoch(control, m):
    path = epoch_path(control, m['epoch'])
    if path.exists():
        raise ValueError(f'epoch {m["epoch"]} exists; epochs are never edited')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(m, indent=1, sort_keys=True))
    tmp = Path(control) / 'CURRENT.tmp'
    tmp.write_text(f"{m['epoch']}\n")
    tmp.replace(Path(control) / 'CURRENT')


def init(control, packages, rules, champion, author, authority, arrival=None):
    control = Path(control)
    if (control / 'CURRENT').exists():
        raise ValueError('control directory already initialised')
    for d in ('epochs', 'queue', 'ratings', 'snapshots', 'results'):
        (control / d).mkdir(parents=True, exist_ok=True)
    events = []
    for pid, p in sorted(packages.items()):
        problems = check_package(p)
        if problems:
            raise ValueError(f'{pid}: {problems}')
        extra = dict(model=arrival(p)) if arrival is not None else {}
        events.append(event('submit', pid, author, authority, kind=p['kind'], package_sha256=sha(p), epoch=0, **extra))
    events.append(event('champion', champion, author, authority, epoch=0))
    append_log(control, events)
    (control / 'rules.json').write_text(json.dumps(rules, indent=1, sort_keys=True))
    st = fold(read_log(control))
    snap = xs.epoch_snapshot({}, 0, 0.0)
    xs.write_snapshot(control / 'snapshots', snap)
    m = make_epoch(1, None, st, packages, rules, snap['id'], applied=[e['seq'] for e in read_log(control)])
    write_epoch(control, m)
    return m


# ---- results ---------------------------------------------------------------------------------

def read_results(control):
    """Every board row, the first written for each (epoch, slot, k): a board written twice (two runners on one control
    directory, which `lock` prevents) counts once."""
    rows, seen = [], set()
    for path in sorted((Path(control) / 'results').glob('e*/slot*.jsonl')):       # board rows; experience-*.jsonl are envelopes
        for l in path.read_text().splitlines():
            if l.strip():
                r = json.loads(l)
                key = (r['epoch'], r['slot'], r['k'])
                if key not in seen:
                    seen.add(key)
                    rows.append(r)
    return rows


def lock(control):
    """An exclusive lock on a control directory for the life of the returned file: a second runner stops at once."""
    import fcntl
    f = (Path(control) / '.runner.lock').open('a+')
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        f.close()
        raise SystemExit(f'another runner holds {control}/.runner.lock')
    return f


def pooled(rows, condition):
    """[(a, b, x)] for one condition, a deal family once per pair, earliest board first (epoch, slot, k)."""
    out, seen = [], set()
    for r in sorted(rows, key=lambda r: (r['epoch'], r['slot'], r['k'])):
        x = r.get(condition)
        if x is None or r.get('training_only'):
            continue
        a, b = r['pair'].split('~')
        if a == b or (r['family'], a, b) in seen:
            continue
        seen.add((r['family'], a, b))
        out.append((a, b, float(x)))
    return out


# ---- the boundary ------------------------------------------------------------------------------

def close_epoch(control, packages, author='controller', source_commit=None, arrival=None):
    """Decide what the results of the current epoch change and open the next epoch. Returns (next manifest, decisions)."""
    control = Path(control)
    rules = json.loads((control / 'rules.json').read_text())
    m = current(control)
    n = m['epoch']
    rows = read_results(control)
    played = [r for r in rows if r['epoch'] == n]
    if len(played) < m['end']['boards']:
        raise ValueError(f'epoch {n} has {len(played)} of {m["end"]["boards"]} boards')
    cond = rules['condition']
    decisions = []
    # 1. ratings, one table per condition
    tables = {}
    for c in ('common', 'native'):
        res = pooled(rows, c)
        if not res:
            continue
        pairs = ar.summarise(res)
        players = sorted({p.i for p in pairs} | {p.j for p in pairs})
        ref = rules['reference'] if rules['reference'] in players else players[0]
        R = ar.fit(pairs, players, ref)
        tables[c] = R
        (control / 'ratings').mkdir(exist_ok=True)
        (control / 'ratings' / f'{n:04d}-{c}.json').write_text(json.dumps(dict(
            schema='ratings-v1', epoch=n, condition=c, reference=ref, t2=R.t2,
            players={p: dict(strength=R.strength(p)[0], se=math.sqrt(R.strength(p)[1])) for p in players},
            pairs=[dict(pair=f'{q.i}~{q.j}', boards=q.n, mean=q.mean) for q in pairs]), indent=1, sort_keys=True))
    st = fold(read_log(control))
    champ = champion_of(st)
    R = tables.get(cond)
    new = []
    # 2. promotion tests: the direct match since the test opened, in board order, fresh capital per test
    for p, s in sorted(st.items()):
        if not s['test'] or s['status'] == 'retired':
            continue
        t = ar.BettingTest(alpha=rules['promotion']['alpha'], beta=rules['promotion']['beta'], d=rules['promotion']['d'], cap=rules['promotion']['cap'])
        name = pair_name(p, s['test']['champion'])
        result = None
        for r in sorted((r for r in rows if r['pair'] == name and r['epoch'] >= s['test']['opened_epoch'] and r.get(cond) is not None),
                        key=lambda r: (r['epoch'], r['slot'], r['k'])):
            result = t.update(float(r[cond]))
            if result:
                break
        evidence = dict(test=name, boards=t.t, K=round(t.K, 4), L=round(t.L, 4), rule=rules['promotion'])
        if result == 'promote':
            new.append(event('promote', p, author, f"rules {rules['version']}: betting test reached 1/alpha", epoch=n, evidence=evidence))
        elif result in ('futility', 'cap'):
            new.append(event('demote', p, author, f"rules {rules['version']}: {result}", epoch=n, evidence=evidence))
        decisions.append(dict(kind='test', player=p, result=result or 'open', **evidence))
    # 3. admission: a candidate whose strength is known to the set width (or has played enough) becomes active;
    #    an active player rated above the champion gets a promotion test
    if R is not None:
        boards = {}
        for a, b, _ in pooled(rows, cond):
            boards[a] = boards.get(a, 0) + 1; boards[b] = boards.get(b, 0) + 1
        for p, s in sorted(st.items()):
            if p not in R.players:
                continue
            se = math.sqrt(R.strength(p)[1]) if p != R.reference else 0.0
            if s['status'] == 'candidate' and (se <= rules['admission']['se'] or boards.get(p, 0) >= rules['admission']['max_boards']):
                new.append(event('activate', p, author, f"rules {rules['version']}: admitted", epoch=n, evidence=dict(se=round(se, 4), boards=boards.get(p, 0))))
                decisions.append(dict(kind='admit', player=p, se=se, boards=boards.get(p, 0)))
        promoted = {e['player'] for e in new if e['event'] == 'promote'}
        activated = {e['player'] for e in new if e['event'] == 'activate'}
        for p, s in sorted(st.items()):
            if (s['status'] == 'active' or p in activated) and not s['test'] and p in R.players and champ in R.players and p not in promoted:
                if R.strength(p)[0] > R.strength(champ)[0] and not any(e['event'] == 'demote' and e['player'] == p for e in new):
                    new.append(event('open-test', p, author, f"rules {rules['version']}: rated above the champion", epoch=n + 1, champion=champ))
                    decisions.append(dict(kind='open-test', player=p, champion=champ))
        # 4. retirement: an unprotected active player far below the champion after the minimum time
        rr = rules['retirement']
        for p, s in sorted(st.items()):
            if s['status'] != 'active' or s['protected'] or s['test'] or p not in R.players or champ not in R.players:
                continue
            if s['since'] is not None and n - s['since'] < rr['min_epochs']:
                continue
            a = np.zeros(len(R.players)); a[R.index(p)] += 1; a[R.index(champ)] -= 1
            gap, sd = float(a @ R.s), math.sqrt(float(a @ R.C @ a))
            if gap + 1.96 * sd < -rr['gap']:
                new.append(event('retire', p, author, f"rules {rules['version']}: more than {rr['gap']} below the champion", epoch=n,
                                 evidence=dict(gap=round(gap, 4), se=round(sd, 4))))
                decisions.append(dict(kind='retire', player=p, gap=gap, se=sd))
    # 5. people's events from the queue (submit, retire, protect, ...), in file-name order
    queued = []
    for path in sorted((control / 'queue').glob('*.json')):
        e = json.loads(path.read_text())
        if e.get('event') == 'submit':
            pkg = packages.get(e['player'])
            problems = check_package(pkg) if pkg else ['no package in configs/players']
            if problems:
                decisions.append(dict(kind='refused', player=e['player'], problems=problems))
                path.rename(path.with_suffix('.refused'))
                continue
            e = dict(e, kind=pkg['kind'], package_sha256=sha(pkg), epoch=n + 1)
            if arrival is not None:
                e['model'] = arrival(pkg)
        queued.append((path, e))
    append_log(control, new + [e for _, e in queued])
    for path, _ in queued:
        path.rename(path.with_suffix('.applied'))
    decisions += [dict(kind='queued', player=e['player'], event=e['event']) for _, e in queued]
    # 6. experience snapshot at the boundary, then the next epoch
    env_files = sorted((control / 'results').glob('e*/experience-*.jsonl*'))
    stores, _ = xs.merge(xs.read(env_files)) if env_files else ({}, None)
    snap = xs.epoch_snapshot(stores, n, max([r.get('completed_epoch', 0) for r in played] or [0]), previous=m['experience_snapshot'])
    xs.write_snapshot(control / 'snapshots', snap)
    st = fold(read_log(control))
    log = read_log(control)
    applied = [e['seq'] for e in log if e['seq'] not in set(_applied_so_far(control))]
    nxt = make_epoch(n + 1, m, st, packages, rules, snap['id'], applied, source_commit=source_commit)
    write_epoch(control, nxt)
    return nxt, decisions


def _applied_so_far(control):
    out = []
    for path in sorted((Path(control) / 'epochs').glob('*.json')):
        out += json.loads(path.read_text()).get('events_applied', [])
    return out


# ---- playing an epoch ------------------------------------------------------------------------

def play_epoch(control, backend, slot=0, workers=1, limit=None, mirror=None):
    """Play the current epoch's boards for one slot with a backend; rows go to results/e<n>/slot<s>.jsonl."""
    m = current(control)
    n, seed, weights = m['epoch'], m['deals']['seed'], m['schedule']['pair_weights']
    out = Path(control) / 'results' / f'e{n:04d}' / f'slot{slot}.jsonl'
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)['k'] for l in out.read_text().splitlines() if l.strip()} if out.exists() else set()
    jobs = {}                                   # pair -> [(k, deal index, floor group or None)]
    floor_total = 0
    for g, fl in enumerate(m['schedule'].get('floors', [])):
        for pi, pair in enumerate(fl['pairs']):
            for j in range(fl['boards']):
                k = FLOOR_BASE + g * FLOOR_GROUP + pi * FLOOR_PAIR + j
                d = FLOOR_BASE + g * FLOOR_GROUP + (j if fl['same_deals'] else pi * FLOOR_PAIR + j)
                jobs.setdefault(pair, []).append((k, deal_index(slot, d), g))
        floor_total += fl['boards'] * len(fl['pairs'])
    rest = m['end']['boards'] - floor_total
    for k in range(rest):
        jobs.setdefault(pair_at(seed, slot, k, weights), []).append((k, deal_index(slot, k), None))
    if limit is not None:
        jobs = {p: v[:limit] for p, v in jobs.items()}
    xp_out = out.parent / f'experience-slot{slot}.jsonl'
    mirror = Path(mirror).open('a') if mirror else None
    with out.open('a') as f, xp_out.open('a') as fx:
        for pair, items in sorted(jobs.items()):
            items = [x for x in items if x[0] not in done]
            if not items:
                continue
            for (k, idx, g), (got, row) in zip(items, backend.play(m, pair, [x[1] for x in items], seed, workers)):
                if got != idx:
                    raise ValueError('the backend answered for another deal')
                envelopes = row.pop('envelopes', None) or []
                for e in envelopes:
                    fx.write(canonical(dict(e, epoch=n)) + '\n')
                fx.flush()
                line = canonical(dict(row, epoch=n, epoch_id=m['id'], slot=slot, k=k, pair=pair, floor=g,
                                      experience_snapshot=m['experience_snapshot'])) + '\n'
                f.write(line)
                f.flush()
                if mirror:                      # a flat copy of every row, for a box queue's progress count
                    mirror.write(line)
                    mirror.flush()
    if mirror:
        mirror.close()
    return out


class SimBackend:
    """Synthetic boards for tests and simulations: each package's bundle carries `sim: {strength, bidding}`;
    a board's common result is the strength gap plus noise, its native result adds the bidding gap. No DDS, no nets."""

    def __init__(self, packages, noise_sd=3.0):
        self.packages, self.noise_sd = packages, noise_sd

    def play(self, m, pair, indices, seed, workers=1):
        a, b = pair.split('~')
        missing = [x for x in (a, b) if 'sim' not in self.packages[x]['bundle']]
        if missing:
            raise ValueError(f'{missing} have no bundle.sim (no synthetic strength): play them with --backend match')
        sa, sb = (self.packages[x]['bundle']['sim'] for x in (a, b))
        for idx in indices:
            rng = np.random.default_rng([seed, idx])
            family = hashlib.sha256(f'{seed}/{idx}'.encode()).hexdigest()
            if a == b:
                yield idx, dict(index=idx, family=family, candidate=a, opponent=b, common=None, native=None, backend='sim')
                continue
            # mostly flat, else a swing of 3 to 13 IMPs (SD 5.6 before scaling), scaled to noise_sd
            noise = float(rng.choice([0.0, 0.0, 0.0, -1.0, 1.0]) * rng.choice([3.0, 6.0, 10.0, 13.0]) + rng.normal(0, 0.5)) * self.noise_sd / 5.6
            common = sa['strength'] - sb['strength'] + noise
            native = common + sa.get('bidding', 0.0) - sb.get('bidding', 0.0)
            yield idx, dict(index=idx, family=family, candidate=a, opponent=b, common=round(common, 3), native=round(native, 3),
                            completed_epoch=float(idx), backend='sim')
