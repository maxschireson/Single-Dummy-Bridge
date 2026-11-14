"""SQLite: accounts, sessions, finished boards and their analyses. Live tables are held in memory (tables.py)."""
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
  imps INTEGER,
  analysis TEXT,
  sid_analysis TEXT,
  replay_of INTEGER,
  personas TEXT
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

# Columns added after the first release; an older file gets them on open.
ADDED_COLUMNS = (('boards', 'analysis', 'TEXT'), ('boards', 'sid_analysis', 'TEXT'), ('boards', 'replay_of', 'INTEGER'),
                 ('boards', 'personas', 'TEXT'))

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
        for table, column, kind in ADDED_COLUMNS:
            have = {r['name'] for r in self.db.execute(f'PRAGMA table_info({table})')}
            if column not in have:
                self.db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {kind}')

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

    def username_free(self, username):
        return self.db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone() is None

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
                'contract', 'declarer', 'tricks', 'claimed', 'ns_score', 'play', 'seats', 'bot', 'bot_identity', 'replay_of',
                'personas')
        values = [json.dumps(record[c]) if c in ('hands', 'calls', 'play', 'seats') else
                  (json.dumps(record[c]) if record.get(c) else None) if c == 'personas' else record.get(c) for c in cols]
        cur = self.db.execute(f'INSERT INTO boards({",".join(cols)}) VALUES ({",".join("?" * len(cols))})', values)
        for seat, user_id, anon in participants:
            self.db.execute('INSERT INTO participants VALUES (?,?,?,?)',
                            (cur.lastrowid, seat, user_id, token_hash(anon) if anon and not user_id else None))
        return cur.lastrowid

    def set_sid_table(self, board_id, sid, sid_ns_score, imps):
        self.db.execute('UPDATE boards SET sid_table=?, sid_ns_score=?, imps=? WHERE id=?',
                        (json.dumps(sid), sid_ns_score, imps, board_id))

    def set_analysis(self, board_id, which, analysis):
        """which: 'analysis' (the human's table) or 'sid_analysis' (Sid's own table on the same deal)."""
        assert which in ('analysis', 'sid_analysis')
        self.db.execute(f'UPDATE boards SET {which}=? WHERE id=?', (json.dumps(analysis), board_id))

    def replay_source(self, board_id, user_id, anon_token):
        """The deal of one of the viewer's boards, with Sid's table and its analysis, for playing it again."""
        b = self.board(board_id, user_id, anon_token)
        if b is None:
            return None
        return dict(id=b['replay_of'] or b['id'], number=b['number'], hands=b['hands'], sid_table=b['sid_table'],
                    sid_analysis=b['sid_analysis'], personas=b['personas'])

    def _owner(self, user_id, anon_token):
        if user_id:
            return 'p.user_id=?', user_id
        return 'p.anon_hash=?', token_hash(anon_token or '')

    def history(self, user_id, anon_token, limit=50, offset=0):
        where, arg = self._owner(user_id, anon_token)
        rows = self.db.execute(
            f'SELECT b.id, b.mode, b.number, b.finished, b.dealer, b.vulnerability, b.contract, b.declarer, b.tricks, '
            f'b.ns_score, b.sid_ns_score, b.imps, b.sid_table, b.replay_of, b.analysis, p.seat FROM boards b '
            f'JOIN participants p ON p.board_id=b.id '
            f'WHERE {where} ORDER BY b.finished DESC, b.id DESC LIMIT ? OFFSET ?', (arg, limit, offset)).fetchall()
        totals = self.db.execute(
            f'SELECT COUNT(*) n, SUM(b.imps) imps, SUM(b.imps IS NOT NULL) compared FROM boards b '
            f'JOIN participants p ON p.board_id=b.id WHERE {where} AND b.replay_of IS NULL', (arg,)).fetchone()
        replays = self.db.execute(f'SELECT COUNT(*) n FROM boards b JOIN participants p ON p.board_id=b.id '
                                  f'WHERE {where} AND b.replay_of IS NOT NULL', (arg,)).fetchone()['n']
        out = []
        for r in rows:
            sid = json.loads(r['sid_table']) if r['sid_table'] else None
            summary = (json.loads(r['analysis']).get('summary') or {}) if r['analysis'] else None
            out.append(dict(id=r['id'], mode=r['mode'], number=r['number'], finished=r['finished'], dealer=r['dealer'],
                            vulnerability=r['vulnerability'], contract=r['contract'], declarer=r['declarer'], tricks=r['tricks'],
                            ns_score=r['ns_score'], seat=r['seat'], imps=r['imps'], sid_ns_score=r['sid_ns_score'],
                            sid_contract=sid and sid.get('contract'), sid_declarer=sid and sid.get('declarer'),
                            sid_tricks=sid and sid.get('tricks'), replay_of=r['replay_of'],
                            lost=summary.get('lost') if summary else None))
        return out, dict(boards=totals['n'], imps=totals['imps'] or 0, compared=totals['compared'] or 0, replays=replays)

    def board(self, board_id, user_id, anon_token):
        where, arg = self._owner(user_id, anon_token)
        r = self.db.execute(f'SELECT b.*, p.seat AS my_seat FROM boards b JOIN participants p ON p.board_id=b.id '
                            f'WHERE b.id=? AND {where}', (board_id, arg)).fetchone()
        if r is None:
            return None
        d = dict(r)
        for k in ('hands', 'calls', 'play', 'seats', 'sid_table', 'analysis', 'sid_analysis', 'personas'):
            d[k] = json.loads(d[k]) if d[k] else None
        return d

    def neighbours(self, board_id, user_id, anon_token):
        """(older, newer) board ids next to this one in the viewer's history."""
        where, arg = self._owner(user_id, anon_token)
        me = self.db.execute('SELECT finished, id FROM boards WHERE id=?', (board_id,)).fetchone()
        if me is None:
            return None, None
        key = (me['finished'], me['id'])
        q = (f'SELECT b.id FROM boards b JOIN participants p ON p.board_id=b.id WHERE {where} AND '
             f'(b.finished, b.id) {{}} (?, ?) ORDER BY b.finished {{}}, b.id {{}} LIMIT 1')
        older = self.db.execute(q.format('<', 'DESC', 'DESC'), (arg, *key)).fetchone()
        newer = self.db.execute(q.format('>', 'ASC', 'ASC'), (arg, *key)).fetchone()
        return (older['id'] if older else None), (newer['id'] if newer else None)
