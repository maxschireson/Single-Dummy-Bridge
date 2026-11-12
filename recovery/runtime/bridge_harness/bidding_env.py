"""Information-legal auctions and cached DDS terminal rewards (no card play).

The 193-feature/40-token interface interoperates with external BEN v3 weights.
No BEN source or weights are distributed by this module. See CREDITS.md.
"""
from dataclasses import dataclass
import ctypes as C
import hashlib
import json
import sqlite3
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

import numpy as np

from .core import Board, auction_contract, normalize_bid, score, vulnerable, imps
from .dds import DDS

CALLS = ('PAD_START', 'PAD_END', 'PASS', 'X', 'XX') + tuple(
    f'{level}{strain}' for level in range(1, 8) for strain in 'CDHSN')
CALL_ID = {c: i for i, c in enumerate(CALLS)}


def deal_key(hands, rotations=False):
    rows = tuple(tuple(sorted(h)) for h in hands)
    if rotations:
        rows = min(rows[i:] + rows[:i] for i in range(4))
    return hashlib.sha256(bytes(c for h in rows for c in h)).hexdigest()


def deal_split(hands):
    bucket = int(deal_key(hands, True)[:8], 16) % 100
    return 'train' if bucket < 80 else 'dev' if bucket < 90 else 'test'


def make_board(seed, index, split):
    """Independent deterministic deals; all rotations/vulnerabilities share a split."""
    if split not in ('train', 'dev', 'test'):
        raise ValueError('Unknown split')
    rng = np.random.default_rng(np.random.SeedSequence([seed, index]))
    while True:
        deck = rng.permutation(52)
        hands = tuple(tuple(sorted(map(int, deck[13*s:13*s+13]))) for s in range(4))
        if deal_split(hands) == split:
            return Board(deal_key(hands), hands, None, int(rng.integers(4)),
                         ('None', 'NS', 'EW', 'Both')[int(rng.integers(4))])


@dataclass(frozen=True)
class BidObservation:
    """Only this object crosses into policy encoding: no board, seed, or DD table."""
    hand: tuple
    seat: int
    dealer: int
    vulnerability: str
    calls: tuple


def encode(obs):
    if len(obs.hand) != 13 or len(set(obs.hand)) != 13:
        raise ValueError('A bidder needs exactly 13 distinct cards')
    if obs.seat != (obs.dealer + len(obs.calls)) % 4:
        raise ValueError('Wrong player to act')
    first_turn = (obs.seat - obs.dealer) % 4
    turns = range(first_turn, len(obs.calls) + 1, 4)
    # Match BEN's float16 feature rounding before conversion to model float32.
    x = np.zeros((len(turns), 193), np.float16)
    hand = np.zeros((4, 6), np.float16)
    for c in obs.hand:
        if not 0 <= c < 52:
            raise ValueError('Invalid card')
        hand[c // 13, min(12-c % 13, 5)] += 1
    x[:, :2] = 1  # pinned GIB-BBO system identifiers, both partnerships
    x[:, 2:4] = (vulnerable(obs.vulnerability, obs.seat),
                  vulnerable(obs.vulnerability, (obs.seat+1) % 4))
    x[:, 4] = (np.sum(hand[:, :4] * np.array([4, 3, 2, 1])) - 10) / 4
    x[:, 5:9] = (hand.sum(axis=1) - np.float16(3.25)) / np.float16(1.75)
    x[:, 9:33] = hand.reshape(24)
    calls = tuple(normalize_bid(c) for c in obs.calls)
    for t, turn in enumerate(turns):
        for j in range(4):
            k = turn-4+j
            token = CALL_ID[calls[k]] if k >= 0 else 0
            x[t, 33+40*j+token] = 1
    return x.astype(np.float32)


def legal_mask(dealer, calls):
    """Use the harness auction validator as the source of truth for legal calls."""
    mask = np.zeros(40, bool)
    for i in range(2, 40):
        try:
            auction_contract(dealer, (*calls, CALLS[i]))
        except ValueError as exc:
            if str(exc) != 'Incomplete auction':
                continue
        mask[i] = True
    if not mask.any():
        raise ValueError('Completed or invalid auction supplied to bidder')
    return mask


def pack_inputs(xs):
    lengths = np.array([len(x) for x in xs], np.int32)
    padded = np.zeros((len(xs), int(lengths.max()), 193), np.float32)
    for i, x in enumerate(xs):
        padded[i, :len(x)] = x
    return padded, lengths


def masked_probabilities(probabilities, mask, epsilon=0.):
    if not 0 <= epsilon < 1:
        raise ValueError('Invalid exploration probability')
    p = np.maximum(probabilities, 1e-12) * mask
    p = p / p.sum(axis=-1, keepdims=True)
    return (1-epsilon)*p + epsilon*mask/mask.sum(axis=-1, keepdims=True)


def terminal_score(board, calls, table):
    c = auction_contract(board.dealer, calls)
    if c is None:
        return 0
    tricks = int(table[c.trump][c.declarer])
    return score(c, tricks, vulnerable(board.vulnerability, c.declarer)) * (
        1 if c.declarer % 2 == 0 else -1)


def paired_auctions(boards, tables, candidate, opponents, rng, *, explore=False, epsilon=0.01):
    """Two rooms per board. Both candidate partnerships share the same IMP reward.

    Opponents are greedy. The candidate samples only during training. Stored
    observations contain the acting player's hand and public past calls only.
    """
    active = [dict(board=i, room=room, calls=[]) for i in range(len(boards)) for room in (0, 1)]
    results = [[None, None] for _ in boards]
    decisions = []
    while active:
        groups = {}
        for item in active:
            b = boards[item['board']]
            seat = (b.dealer + len(item['calls'])) % 4
            learning = seat % 2 == item['room']
            policy = candidate if learning else opponents[item['board']]
            obs = BidObservation(b.hands[seat], seat, b.dealer, b.vulnerability, tuple(item['calls']))
            groups.setdefault(id(policy), (policy, []))[1].append(
                (item, encode(obs), legal_mask(b.dealer, item['calls']), learning))
        next_active = []
        for policy, group in groups.values():
            xs, lengths = pack_inputs([row[1] for row in group])
            probs, values = policy.predict(xs, lengths)
            for j, (item, x, mask, learning) in enumerate(group):
                use_exploration = learning and explore
                p = masked_probabilities(probs[j], mask, epsilon if use_exploration else 0.)
                action = int(rng.choice(40, p=p/p.sum())) if use_exploration else int(np.argmax(p))
                if use_exploration:
                    decisions.append(dict(x=x, mask=mask, action=action, old_logp=float(np.log(p[action])),
                                          old_value=float(values[j]), pair=item['board']))
                item['calls'].append(CALLS[action])
                if len(item['calls']) > 320:
                    raise RuntimeError('Auction exceeds the legal length bound')
                b = boards[item['board']]
                try:
                    c = auction_contract(b.dealer, item['calls'])
                except ValueError as exc:
                    if str(exc) != 'Incomplete auction':
                        raise
                    next_active.append(item)
                    continue
                results[item['board']][item['room']] = dict(
                    calls=item['calls'], contract=c.text() if c else None,
                    declarer=c.declarer if c else None,
                    ns_score=terminal_score(b, item['calls'], tables[item['board']]))
        active = next_active
    rows = [dict(deal_id=deal_key(b.hands, True), tables=r,
                 imps=imps(r[0]['ns_score']-r[1]['ns_score'])) for b, r in zip(boards, results)]
    for d in decisions:
        d['reward'] = rows[d['pair']]['imps']
    return rows, decisions


class TableDeal(C.Structure):
    _fields_ = [('cards', (C.c_uint * 4) * 4)]


class TableResults(C.Structure):
    _fields_ = [('res', (C.c_int * 4) * 5)]


class TableSolver:
    def __init__(self, library=None):
        self.dds = DDS(library)
        self.dds.lib.dds_c_calc_dd_table.argtypes = [C.c_void_p, C.POINTER(TableDeal), C.POINTER(TableResults)]
        self.dds.lib.dds_c_calc_dd_table.restype = C.c_int

    def solve(self, hands):
        if any(len(h) != 13 for h in hands):
            raise ValueError('DDS tables require a complete deal')
        d = DDS._deal(hands, 4, 0, ())
        inp, out = TableDeal(), TableResults()
        C.memmove(C.addressof(inp), C.addressof(d.hands), C.sizeof(inp))
        status = self.dds.lib.dds_c_calc_dd_table(self.dds.ctx, C.byref(inp), C.byref(out))
        if status != 1:
            raise RuntimeError(f'DDS table error {status}')
        result = [[int(v) for v in row] for row in out.res]
        if not all(0 <= v <= 13 for row in result for v in row):
            raise RuntimeError('Invalid DDS trick count')
        return result


_worker_solver = None


def _init_solver(library):
    global _worker_solver
    _worker_solver = TableSolver(library)


def _solve(hands):
    return _worker_solver.solve(hands)


class TableCache:
    """Only the parent writes SQLite; each solver process owns a DDS context."""
    def __init__(self, path, library, workers=1):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS tables (key TEXT PRIMARY KEY, split TEXT, data TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)')
        identity = hashlib.sha256(Path(library).read_bytes()).hexdigest()
        old = self.db.execute("SELECT value FROM metadata WHERE key='solver_sha256'").fetchone()
        if old and old[0] != identity:
            raise ValueError('DDS library differs from cached provenance')
        self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('solver_sha256', ?)", (identity,))
        self.db.commit()
        self.pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
                                        initializer=_init_solver, initargs=(str(library),))
        self.hits = self.misses = 0

    def get_many(self, boards, progress=None):
        result, missing = {}, []
        for b in boards:
            key = deal_key(b.hands)
            row = self.db.execute('SELECT split,data FROM tables WHERE key=?', (key,)).fetchone()
            if row:
                if row[0] != deal_split(b.hands):
                    raise ValueError('Cache split mismatch')
                result[key] = json.loads(row[1]); self.hits += 1
            else:
                missing.append(b)
        futures = [self.pool.submit(_solve, b.hands) for b in missing]
        for i, (b, f) in enumerate(zip(missing, futures)):
            table = f.result()
            key = deal_key(b.hands)
            self.db.execute('INSERT INTO tables VALUES (?,?,?)', (key, deal_split(b.hands), json.dumps(table)))
            self.db.commit()
            result[key] = table; self.misses += 1
            if progress and (i % 16 == 0 or i == len(missing)-1):
                progress(i+1, len(missing))
        return [result[deal_key(b.hands)] for b in boards]

    def counts(self):
        return dict(self.db.execute('SELECT split,COUNT(*) FROM tables GROUP BY split'))

    def close(self):
        self.pool.shutdown()
        self.db.close()
