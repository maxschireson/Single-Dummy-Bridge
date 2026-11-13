"""SQLite: accounts, sessions and finished boards. Live tables are held in memory (tables.py)."""
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  username TEXT NOT NULL UNIQUE COLLATE NOCASE,
  pw_hash TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created REAL NOT NULL,
  last_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS boards (
  id INTEGER PRIMARY KEY,
  table_id TEXT NOT NULL,
  mode TEXT NOT NULL,
  number INTEGER NOT NULL,
  started REAL NOT NULL,
  finished REAL NOT NULL,
  dealer TEXT NOT NULL,
  vulnerability TEXT NOT NULL,
  hands TEXT NOT NULL,
  calls TEXT NOT NULL,
  contract TEXT,
  declarer TEXT,
  tricks INTEGER,
  claimed INTEGER,
  ns_score INTEGER NOT NULL,
  play TEXT NOT NULL,
  seats TEXT NOT NULL,
  bot TEXT NOT NULL,
  bot_identity TEXT,
  sid_table TEXT,
  sid_ns_score INTEGER,
  imps INTEGER
);
CREATE TABLE IF NOT EXISTS participants (
  board_id INTEGER NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
  seat TEXT NOT NULL,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  anon_hash TEXT,
  PRIMARY KEY (board_id, seat)
);
CREATE INDEX IF NOT EXISTS participants_user ON participants(user_id);
CREATE INDEX IF NOT EXISTS participants_anon ON participants(anon_hash);
"""

SCRYPT = dict(n=2 ** 14, r=8, p=1)


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${salt.hex()}${digest.hex()}"


def check_password(password, stored):
    try:
        kind, n, r, p, salt, digest = stored.split('$')
        if kind != 'scrypt':
            return False
        mine = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), dklen=32, n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(mine.hex(), digest)
    except (ValueError, TypeError):
        return False


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript(SCHEMA)

    # ---- accounts ------------------------------------------------------------------------
    def create_user(self, username, password):
        try:
            cur = self.db.execute('INSERT INTO users(username, pw_hash, created) VALUES (?,?,?)',
                                  (username, hash_password(password), time.time()))
        except sqlite3.IntegrityError:
            return None
        return cur.lastrowid

    def authenticate(self, username, password):
        row = self.db.execute('SELECT id, pw_hash FROM users WHERE username=?', (username,)).fetchone()
        if row is None:
            check_password(password, hash_password('timing-equaliser'))
            return None
        return row['id'] if check_password(password, row['pw_hash']) else None

    def username(self, user_id):
        row = self.db.execute('SELECT username FROM users WHERE id=?', (user_id,)).fetchone()
        return row['username'] if row else None

    def new_session(self, user_id):
        token = secrets.token_urlsafe(32)
        now = time.time()
        self.db.execute('INSERT INTO sessions VALUES (?,?,?,?)', (token_hash(token), user_id, now, now))
        return token

    def session_user(self, token, max_age):
        if not token:
            return None
        row = self.db.execute('SELECT user_id, last_seen FROM sessions WHERE token_hash=?', (token_hash(token),)).fetchone()
        if row is None or time.time() - row['last_seen'] > max_age:
            return None
        if time.time() - row['last_seen'] > 3600:
            self.db.execute('UPDATE sessions SET last_seen=? WHERE token_hash=?', (time.time(), token_hash(token)))
        return row['user_id']

    def end_session(self, token):
        if token:
            self.db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(token),))

    def adopt_anonymous(self, anon_token, user_id):
        """Boards played anonymously in this browser become the account's."""
        if anon_token:
            self.db.execute('UPDATE participants SET user_id=?, anon_hash=NULL WHERE anon_hash=? AND user_id IS NULL',
                            (user_id, token_hash(anon_token)))

    # ---- boards --------------------------------------------------------------------------
    def save_board(self, record, participants):
        """record: dict of board columns. participants: [(seat, user_id or None, anon_token or None)]."""
        cols = ('table_id', 'mode', 'number', 'started', 'finished', 'dealer', 'vulnerability', 'hands', 'calls',
                'contract', 'declarer', 'tricks', 'claimed', 'ns_score', 'play', 'seats', 'bot', 'bot_identity')
        values = [json.dumps(record[c]) if c in ('hands', 'calls', 'play', 'seats') else record[c] for c in cols]
        cur = self.db.execute(f'INSERT INTO boards({",".join(cols)}) VALUES ({",".join("?" * len(cols))})', values)
        for seat, user_id, anon in participants:
            self.db.execute('INSERT INTO participants VALUES (?,?,?,?)',
                            (cur.lastrowid, seat, user_id, token_hash(anon) if anon and not user_id else None))
        return cur.lastrowid

    def set_sid_table(self, board_id, sid, sid_ns_score, imps):
        self.db.execute('UPDATE boards SET sid_table=?, sid_ns_score=?, imps=? WHERE id=?',
                        (json.dumps(sid), sid_ns_score, imps, board_id))

    def _owner(self, user_id, anon_token):
        if user_id:
            return 'p.user_id=?', user_id
        return 'p.anon_hash=?', token_hash(anon_token or '')

    def history(self, user_id, anon_token, limit=50, offset=0):
        where, arg = self._owner(user_id, anon_token)
        rows = self.db.execute(
            f'SELECT b.id, b.mode, b.number, b.finished, b.dealer, b.vulnerability, b.contract, b.declarer, b.tricks, '
            f'b.ns_score, b.sid_ns_score, b.imps, b.sid_table, p.seat FROM boards b JOIN participants p ON p.board_id=b.id '
            f'WHERE {where} ORDER BY b.finished DESC LIMIT ? OFFSET ?', (arg, limit, offset)).fetchall()
        totals = self.db.execute(
            f'SELECT COUNT(*) n, SUM(b.imps) imps, SUM(b.imps IS NOT NULL) compared FROM boards b '
            f'JOIN participants p ON p.board_id=b.id WHERE {where}', (arg,)).fetchone()
        out = []
        for r in rows:
            sid = json.loads(r['sid_table']) if r['sid_table'] else None
            out.append(dict(id=r['id'], mode=r['mode'], number=r['number'], finished=r['finished'], dealer=r['dealer'],
                            vulnerability=r['vulnerability'], contract=r['contract'], declarer=r['declarer'], tricks=r['tricks'],
                            ns_score=r['ns_score'], seat=r['seat'], imps=r['imps'], sid_ns_score=r['sid_ns_score'],
                            sid_contract=sid and sid.get('contract'), sid_declarer=sid and sid.get('declarer'),
                            sid_tricks=sid and sid.get('tricks')))
        return out, dict(boards=totals['n'], imps=totals['imps'] or 0, compared=totals['compared'] or 0)

    def board(self, board_id, user_id, anon_token):
        where, arg = self._owner(user_id, anon_token)
        r = self.db.execute(f'SELECT b.*, p.seat AS my_seat FROM boards b JOIN participants p ON p.board_id=b.id '
                            f'WHERE b.id=? AND {where}', (board_id, arg)).fetchone()
        if r is None:
            return None
        d = dict(r)
        for k in ('hands', 'calls', 'play', 'seats', 'sid_table'):
            d[k] = json.loads(d[k]) if d[k] else None
        return d
