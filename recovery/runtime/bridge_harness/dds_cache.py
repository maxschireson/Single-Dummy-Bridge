"""Persistent exact all-legal-move DDS results, shared by training and evaluation.

Keys contain the complete solver position, never an actual hidden training hand
substituted for a sampled world. No policy/auction/contract-level information is
needed: DD remaining tricks depend only on cards, strain, leader, current trick.
"""
import hashlib
from pathlib import Path
import sqlite3
import struct


def position_key(deal):
    partial = [deal.suits[i]*13 + deal.ranks[i]-2 if deal.ranks[i] else 255 for i in range(3)]
    return struct.pack('<BB3B16H',deal.trump,deal.first,*partial,
                       *(deal.hands[h][s] for h in range(4) for s in range(4)))


def validate_positions(deals, fixed_seats=()):
    """Mirror native batch invariants BEFORE reading hits or solving misses."""
    first = deals[0]
    universe = None
    for d in deals:
        if d.trump not in range(5) or d.first not in range(4):
            raise ValueError('Invalid strain or leader')
        counts = [sum(int(d.hands[h][s]).bit_count() for s in range(4)) for h in range(4)]
        for i in range(3):
            if not d.ranks[i]:
                break
            seat = (d.first+i)%4
            counts[seat] += 1
            if i and d.suits[i] != d.suits[0] and d.hands[seat][d.suits[0]]:
                raise ValueError('Current trick revokes while holding led suit')
        if not 1 <= counts[0] <= 13 or any(c != counts[0] for c in counts):
            raise ValueError('Hands have inconsistent card counts')
        live = tuple(sum(d.hands[h][s] for h in range(4)) for s in range(4))
        # _deal already rejected duplicate cards and malformed/current trick.
        if universe is None:
            universe = live
        elif live != universe:
            raise ValueError('Remaining deck differs across batch')
        if any(d.hands[h][s] != first.hands[h][s] for h in fixed_seats for s in range(4)):
            raise ValueError('Fixed hand differs across batch')


class PositionCache:
    def __init__(self, path, library):
        path = Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        # Isolate solver builds and output semantics. Tables may coexist safely.
        self.namespace = hashlib.sha256(b'dds-all-moves-v1\0'+Path(library).read_bytes()).digest()
        self.db = sqlite3.connect(path,timeout=60)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS positions ('
                        'solver BLOB NOT NULL, position BLOB NOT NULL, scores BLOB NOT NULL,'
                        'PRIMARY KEY(solver,position)) WITHOUT ROWID')
        self.db.commit()

    def get_many(self, keys):
        found = {}
        keys = list(dict.fromkeys(keys))
        for start in range(0,len(keys),500):
            part = keys[start:start+500]
            marks = ','.join('?' for _ in part)
            rows = self.db.execute(f'SELECT position,scores FROM positions WHERE solver=? AND position IN ({marks})',
                                   [self.namespace,*part])
            for key,data in rows:
                if len(data)!=52 or any(v>14 for v in data):
                    raise ValueError('Corrupt DDS cache result')
                found[key] = {c:v-1 for c,v in enumerate(data) if v}
        return found

    def put_many(self, rows):
        encoded = []
        for key,scores in rows:
            values = bytearray(52)
            if not scores:
                raise ValueError('Empty DDS result cannot be cached')
            for c,t in scores.items():
                if c not in range(52) or t not in range(14):
                    raise ValueError('Invalid DDS result')
                values[c] = t+1
            encoded.append((self.namespace,key,bytes(values)))
        with self.db:
            self.db.executemany('INSERT OR IGNORE INTO positions VALUES (?,?,?)',encoded)
            for namespace,key,data in encoded:
                stored = self.db.execute('SELECT scores FROM positions WHERE solver=? AND position=?',
                                         (namespace,key)).fetchone()[0]
                if stored != data:
                    raise ValueError('Conflicting exact DDS cache results')

    def close(self):
        if self.db is not None:
            self.db.close()
            self.db = None

    def backup(self, destination):
        """Consistent portable snapshot, including committed WAL transactions."""
        destination = Path(destination)
        if destination.exists():
            raise ValueError('Refusing to overwrite a cache snapshot')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(destination) as db:
            self.db.backup(db)
