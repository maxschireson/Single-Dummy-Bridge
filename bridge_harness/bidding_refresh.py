"""Clean, provenance-checked outcome rewards for a bidding mix experiment.

Observed tricks may be reused across levels/doubles, but never across strain,
declarer, deal orientation, dealer or vulnerability. Unobserved contracts abstain.
This is a partial-support experiment, not an unbiased off-policy evaluation.
"""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3

import numpy as np

from .bidding_env import (BidObservation, CALLS, encode, legal_mask, pack_inputs,
                          masked_probabilities, deal_key, make_board)
from .core import Board, auction_contract, imps, score, vulnerable
from .runner import replay

BAD_POLICY = 'e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed'
BAD_BOTS = {'4', '4p', 'v4', 'v4p', 'P'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def clean_actors(manifest, actor_bots):
    """Fail closed: inspect every actually assigned actor, not unused manifest bots."""
    if not actor_bots:
        return False
    for bot in actor_bots.values():
        spec = manifest.get('bots', {}).get(bot)
        if spec is None or bot in BAD_BOTS:
            return False
        hashes = spec.get('artifact_sha256', {})
        if hashes.get('policy') == BAD_POLICY:
            return False
        if spec.get('policy') and not hashes.get('policy'):
            return False
    return True


def play_split(family):
    # Preserve the arena's hash%5 train/validation boundary; reserve half of
    # validation as a final test before choosing mixes.
    bucket = int(family[:8], 16) % 10
    return 'test' if bucket == 0 else 'dev' if bucket == 5 else 'train'


def board_key(board):
    return digest([board.hands, board.dealer, board.vulnerability])


def prepare_play(export_root, local_runs):
    pools, seen, sources = {}, set(), []
    counts = Counter()

    def add(game, manifest, actor_bots, path, expected_sha=None):
        if not clean_actors(manifest, actor_bots):
            counts['rejected_policy_games'] += 1
            return
        if set(game['assignments']) - set(actor_bots):
            raise ValueError('Unresolved active actor')
        if expected_sha and sha(path) != expected_sha:
            raise ValueError('Export checksum mismatch')
        b = Board.from_dict(game['board'])
        family = deal_key(b.hands, True)
        if game.get('family', family) != family:
            raise ValueError('Wrong deal family')
        table = game['tables'][0]
        if b.contract is not None:
            replay(game)
            if len(table['actions']) != 52:
                raise ValueError('Incomplete play')
            expected = score(b.contract, table['declarer_tricks'],
                             vulnerable(b.vulnerability, b.contract.declarer))
            expected *= 1 if b.contract.declarer % 2 == 0 else -1
            if expected != table['ns_score']:
                raise ValueError('Inconsistent final score')
        elif table['ns_score'] != 0:
            raise ValueError('Passed-out nonzero score')
        # Deduplicate full trajectories across exports, sources and auction regimes.
        signature = digest([board_key(b), b.auction,
                            [actor_bots[a] for a in game['assignments']],
                            [(a['seat'], a['card']) for a in table['actions']],
                            table.get('declarer_tricks')])
        if signature in seen:
            counts['duplicate_games'] += 1
            return
        seen.add(signature)
        key = board_key(b)
        row = pools.setdefault(key, dict(board=b.to_dict(), family=family,
                    split=play_split(family), source='play', outcomes={}, games=0))
        row['games'] += 1
        if b.contract is not None:
            slot = f'{b.contract.trump}/{b.contract.declarer}'
            row['outcomes'].setdefault(slot, []).append(int(table['declarer_tricks']))
        counts['retained_games'] += 1
        sources.append(dict(path=str(path), sha256=sha(path), trajectory=signature,
                            family=family, actor_bots=actor_bots))

    export_root = Path(export_root)
    provenance = json.loads((export_root/'provenance.json').read_text())
    manifests = {}
    for item in provenance:
        run = item['source_run']
        if run not in manifests:
            manifests[run] = json.loads((export_root/'runs'/run/'manifest.json').read_text())
        path = export_root/item['file']
        with gzip.open(path, 'rt') as f:
            add(json.load(f), manifests[run], item['actor_bots'], path, item['sha256'])
    for run in local_runs:
        run = Path(run)
        manifest = json.loads((run/'manifest.json').read_text())
        files = sorted((run/'episodes').glob('*.json.gz'))
        for path in files:
            with gzip.open(path, 'rt') as f:
                record = json.load(f)
            if record.get('schema') != 'v4-two-auction-arena-v1':
                raise ValueError('Unsupported local record schema')
            mapping = {'candidate': record['candidate'], 'opponent': record['opponent']}
            for game in record['unique_tables'].values():
                active = {a: mapping[a] for a in game['assignments']}
                add(game, manifest, active, path)
    rows = sorted(pools.values(), key=lambda r: (r['family'], board_key(Board.from_dict(r['board']))))
    for split in ('train', 'dev', 'test'):
        counts['families_'+split] = len({r['family'] for r in rows if r['split'] == split})
    counts['unique_families'] = len({r['family'] for r in rows})
    return rows, dict(counts), sources


def recover_dds(checkpoint):
    """Regenerate original hands and read existing cached labels; never solve."""
    checkpoint = Path(checkpoint)
    cfg = json.loads((checkpoint/'run/manifest.json').read_text())['config']
    state = json.loads((checkpoint/'run/state.json').read_text())
    db = sqlite3.connect(f'file:{checkpoint / "run/dds.sqlite"}?mode=ro', uri=True)
    rows = []
    for split, n, seed in [('train', state['trained_pairs'], cfg['seed']+100003),
                           ('dev', cfg['dev_pairs'], cfg['seed']+100003+50000000)]:
        for index in range(n):
            b = make_board(seed, index, split)
            found = db.execute('SELECT data FROM tables WHERE key=?', (deal_key(b.hands),)).fetchone()
            if not found:
                raise ValueError('Original DDS cache does not cover reconstructed deal')
            rows.append(dict(board=b.to_dict(), family=deal_key(b.hands, True), split=split,
                             source='dds', dds=json.loads(found[0])))
    db.close()
    return rows


def terminal_scores(board, calls, reward):
    c = auction_contract(board.dealer, calls)
    if c is None:
        return [0], 'passed_out'
    slot = f'{c.trump}/{c.declarer}'
    exact = reward.get('auction_outcomes')
    if exact is not None and exact.get(digest(list(calls))):
        tricks = exact[digest(list(calls))]['tricks']
        source = 'clean_play_exact_auction'
    elif exact is None and reward.get('outcomes', {}).get(slot):
        tricks = reward['outcomes'][slot]
        source = 'clean_play_reused'
    elif reward.get('dds') is not None:
        tricks = [reward['dds'][c.trump][c.declarer]]
        source = 'dds'
    else:
        return None, 'unobserved'
    sign = 1 if c.declarer % 2 == 0 else -1
    return [sign*score(c, int(t), vulnerable(board.vulnerability, c.declarer)) for t in tricks], source


def expected_imps(left, right):
    return float(np.mean([imps(a-b) for a in left for b in right]))


def auction_pairs(rewards, candidate, opponent, rng, explore=False, epsilon=.005, missing_score=None, keep_unscored=False):
    """Fresh on-policy auctions; historical greedy calls are never PPO samples."""
    boards = [Board.from_dict(r['board']) for r in rewards]
    active = [dict(board=i, room=room, calls=[]) for i in range(len(boards)) for room in (0, 1)]
    rooms, decisions = [[None, None] for _ in boards], []
    while active:
        groups = {}
        for item in active:
            b = boards[item['board']]
            seat = (b.dealer+len(item['calls'])) % 4
            learning = seat % 2 == item['room']
            policy = candidate if learning else opponent
            x = encode(BidObservation(b.hands[seat], seat, b.dealer, b.vulnerability, tuple(item['calls'])))
            groups.setdefault(id(policy), (policy, []))[1].append((item, x, legal_mask(b.dealer, item['calls']), learning))
        active = []
        for policy, group in groups.values():
            xs, lengths = pack_inputs([g[1] for g in group])
            raw, values = policy.predict(xs, lengths)
            for j, (item, x, mask, learning) in enumerate(group):
                sampled = explore and learning
                p = masked_probabilities(raw[j], mask, epsilon if sampled else 0.)
                action = int(rng.choice(40, p=p/p.sum())) if sampled else int(np.argmax(p))
                if sampled:
                    decisions.append(dict(x=x, mask=mask, action=action, old_logp=float(np.log(p[action])),
                                          old_value=float(values[j]), pair=item['board']))
                item['calls'].append(CALLS[action])
                if len(item['calls']) > 320:
                    raise ValueError('Auction exceeds legal bound')
                b = boards[item['board']]
                try:
                    c = auction_contract(b.dealer, item['calls'])
                except ValueError as exc:
                    if str(exc) != 'Incomplete auction':
                        raise
                    active.append(item)
                    continue
                scores, source = terminal_scores(b, item['calls'], rewards[item['board']])
                rooms[item['board']][item['room']] = dict(calls=item['calls'],
                    contract=c.text() if c else None, declarer=c.declarer if c else None,
                    ns_scores=scores, reward_source=source)
    missing = [(i, room) for i, pair in enumerate(rooms) for room, r in enumerate(pair)
               if r['ns_scores'] is None]
    if missing and missing_score is not None:
        requests = [(boards[i], rooms[i][room]['calls']) for i, room in missing]
        owner = getattr(missing_score, '__self__', None)
        resolved = (owner.resolve_many(requests) if owner is not None and hasattr(owner,'resolve_many')
                    else [missing_score(b,calls) for b,calls in requests])
        for (i, room), (scores, source) in zip(missing, resolved):
            rooms[i][room].update(ns_scores=scores,reward_source=source)
    rows = []
    for reward, pair in zip(rewards, rooms):
        scores = [p['ns_scores'] for p in pair]
        rows.append(dict(family=reward['family'], tables=pair,
                         imps=expected_imps(*scores) if all(s is not None for s in scores) else None))
    accepted = []
    for d in decisions:
        value = rows[d['pair']]['imps']
        if value is not None or keep_unscored:
            d['reward'] = value
            accepted.append(d)
    return rows, accepted


def common_support(evaluations):
    """Same deal set for every candidate; no model-specific cherry-picking."""
    keys = None
    for rows in evaluations.values():
        valid = {r['family'] for r in rows if r['imps'] is not None}
        keys = valid if keys is None else keys & valid
    return sorted(keys or [])


def clustered_summary(rows, families=None):
    groups = {}
    for row in rows:
        if row['imps'] is not None and (families is None or row['family'] in families):
            groups.setdefault(row['family'], []).append(row['imps'])
    values = np.array([np.mean(v) for v in groups.values()])
    n = len(values)
    mean = float(values.mean()) if n else None
    se = float(values.std(ddof=1)/np.sqrt(n)) if n > 1 else None
    return dict(families=n, mean_imps=mean, se=se,
                ci95=[mean-1.96*se, mean+1.96*se] if se is not None else None,
                informative=bool(n > 1 and se > 0))
