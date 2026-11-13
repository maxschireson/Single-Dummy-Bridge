"""Play server against the stand-in bot (no models): full boards, hidden-card boundary, accounts, pairs, claims.

  cd play && SIDPLAY_ENGINE=fake python -m pytest tests -q
"""
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.update(SIDPLAY_ENGINE='fake', SIDPLAY_DATA=tempfile.mkdtemp(), SIDPLAY_PACE='0', SIDPLAY_TRICK_PAUSE='0',
                  SIDPLAY_WORKERS='2', SIDPLAY_BACKGROUND_WORKERS='1', SIDPLAY_SOURCE=str(ROOT.parent))
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient   # noqa: E402
from sidplay import app as appmod, fake_engine   # noqa: E402

H = {'X-Sid': '1'}
SEATS = 'NESW'


@pytest.fixture(scope='module')
def server():
    with TestClient(appmod.app) as c:
        yield c


def fresh(server):
    c = TestClient(server.app)
    c.portal = server.portal            # share the running server loop and its state
    return c


def state(c, tid, since=-1):
    r = c.get(f'/api/tables/{tid}', params={'since': since})
    assert r.status_code == 200, r.text
    return r.json()


def check_boundary(s):
    """Hands a viewer may see: own; dummy and (if they control it) declarer after the lead; all when done."""
    b = s['board']
    me = s['me']
    visible = {k for k, v in b['hands'].items() if v['cards'] is not None}
    if b['phase'] == 'done':
        assert visible == set(SEATS)
        return
    allowed = {me}
    if b['phase'] == 'play' and b['played'] > 0:
        allowed.add(b['dummy'])
        if s['mode'] == 'solo' and b['declarer'] in 'NS':
            allowed.add(b['declarer'])
    assert visible <= allowed, (visible, allowed, b['phase'])
    assert me in visible


def play_board(c, tid, bid_first='1N', claim_at=None, timeout=60):
    """Act whenever it is this client's turn until the board is done. Returns the final state."""
    s = state(c, tid)
    deadline = time.time() + timeout
    while time.time() < deadline:
        check_boundary(s)
        b = s['board']
        if b['phase'] == 'done':
            return s
        if b['turn'] and b['turn']['mine']:
            if b['turn']['kind'] == 'call':
                call = bid_first if bid_first in b['legal'] and not any(x != 'PASS' for x in b['calls']) else 'PASS'
                r = c.post(f'/api/tables/{tid}/call', json={'call': call}, headers=H)
            else:
                if claim_at is not None and b['played'] >= claim_at and b['can_claim']:
                    r = c.post(f'/api/tables/{tid}/claim', json={'tricks': b['remaining']}, headers=H)
                    claim_at = None
                else:
                    r = c.post(f'/api/tables/{tid}/card', json={'card': b['legal'][0]}, headers=H)
            assert r.status_code == 200, r.text
            s = state(c, tid)
        else:
            s = state(c, tid, s['version'])
    raise AssertionError('board did not finish')


def wait_for(c, tid, pred, timeout=20):
    deadline = time.time() + timeout
    s = state(c, tid)
    while not pred(s):
        assert time.time() < deadline, 'timed out'
        s = state(c, tid, s['version'])
    return s


def test_post_needs_header(server):
    assert server.post('/api/tables', json={'mode': 'solo'}).status_code == 400


def test_solo_boards_and_scores(server):
    server.get('/api/me')
    tid = server.post('/api/tables', json={'mode': 'solo'}, headers=H).json()['table']
    s = state(server, tid)
    assert s['me'] == 'S' and [x['kind'] for x in s['seats']] == ['bot', 'bot', 'human', 'bot']
    for n in (1, 2, 3):
        s = play_board(server, tid)
        assert s['board']['number'] == n and s['board']['result'] is not None
        s = wait_for(server, tid, lambda s: s['board']['sid'] not in ('pending', None))
        row = s['scores'][-1]
        assert row['imps'] is not None and row['sid']['ns_score'] is not None
        assert server.post(f'/api/tables/{tid}/next', json={}, headers=H).status_code == 200
    assert len(state(server, tid)['scores']) == 3
    hist = server.get('/api/history').json()
    assert hist['totals']['boards'] == 3 and hist['user'] is None
    detail = server.get(f"/api/boards/{hist['boards'][0]['id']}").json()
    assert len(detail['hands']) == 4 and detail['seats'][2]['kind'] == 'human' and 'user_id' not in detail['seats'][2]


def test_not_your_turn_and_illegal(server):
    tid = server.post('/api/tables', json={'mode': 'solo'}, headers=H).json()['table']
    s = wait_for(server, tid, lambda s: s['board']['turn'] and s['board']['turn']['mine'])
    r = server.post(f'/api/tables/{tid}/card', json={'card': 'SA'}, headers=H)
    assert r.status_code == 409 and 'not your turn' in r.json()['error']
    if any(x != 'PASS' for x in s['board']['calls']):
        r = server.post(f'/api/tables/{tid}/call', json={'call': 'XX'}, headers=H)
        assert r.status_code == 409


def test_claims(server):
    fake_engine.FAKE_DD = 0
    try:
        tid = server.post('/api/tables', json={'mode': 'solo'}, headers=H).json()['table']
        # 7NT is legal at South's first turn whatever came before, and the stand-in bot passes after any bid.
        s = wait_for(server, tid, lambda s: s['board']['turn'] and s['board']['turn']['mine'])
        assert server.post(f'/api/tables/{tid}/call', json={'call': '7NT'}, headers=H).status_code == 200
        s = wait_for(server, tid, lambda s: s['board']['phase'] == 'play' and s['board']['can_claim']
                     and s['board']['turn'] and s['board']['turn']['mine'])
        assert s['board']['contract'] == '7NT' and s['board']['declarer'] in 'NS'   # Sid-North may have bid notrump first
        r = server.post(f'/api/tables/{tid}/claim', json={'tricks': s['board']['remaining']}, headers=H)
        assert r.status_code == 200
        s = state(server, tid)
        # Refused, and the refusal says nothing about how many tricks were there.
        assert s['board']['claim'] == {'seat': 'S', 'tricks': s['board']['remaining'], 'accepted': False}
        assert s['board']['phase'] == 'play'
        assert server.post(f'/api/tables/{tid}/claim', json={'tricks': 99}, headers=H).status_code == 409
        fake_engine.FAKE_DD = None
        played_tricks = s['board']['tricks']['declarer']
        assert server.post(f'/api/tables/{tid}/claim', json={'tricks': s['board']['remaining']}, headers=H).status_code == 200
        s = state(server, tid)
        assert s['board']['phase'] == 'done' and s['board']['result']['claimed'] == 13 - s['board']['played'] // 4
        assert s['board']['result']['tricks'] == played_tricks + s['board']['result']['claimed']
    finally:
        fake_engine.FAKE_DD = None


def test_accounts_adopt_guest_boards(server):
    c = fresh(server)
    c.get('/api/me')
    tid = c.post('/api/tables', json={'mode': 'solo'}, headers=H).json()['table']
    play_board(c, tid)
    assert c.get('/api/history').json()['totals']['boards'] == 1
    assert c.post('/api/signup', json={'username': 'ab', 'password': 'longenough'}, headers=H).status_code == 400
    assert c.post('/api/signup', json={'username': 'alice', 'password': 'short'}, headers=H).status_code == 400
    r = c.post('/api/signup', json={'username': 'alice', 'password': 'longenough'}, headers=H)
    assert r.status_code == 200
    me = c.get('/api/me').json()
    assert me['user'] == 'alice' and me['table'] == tid          # the open table followed the guest into the account
    h = c.get('/api/history').json()
    assert h['user'] == 'alice' and h['totals']['boards'] == 1
    state(c, tid)                                                   # still seated
    c.post('/api/logout', json={}, headers=H)
    assert c.get('/api/me').json()['user'] is None
    assert c.post('/api/login', json={'username': 'alice', 'password': 'wrongpass1'}, headers=H).status_code == 401
    assert c.post('/api/login', json={'username': 'ALICE', 'password': 'longenough'}, headers=H).status_code == 200
    assert c.post('/api/signup', json={'username': 'Alice', 'password': 'longenough'}, headers=H).status_code == 409


def test_pair_table(server):
    a, b, stranger = fresh(server), fresh(server), fresh(server)
    a.post('/api/signup', json={'username': 'north_s', 'password': 'longenough'}, headers=H)
    b.post('/api/signup', json={'username': 'south_n', 'password': 'longenough'}, headers=H)
    stranger.get('/api/me')
    assert stranger.post('/api/tables', json={'mode': 'pair'}, headers=H).status_code == 409   # guests cannot host
    tid = a.post('/api/tables', json={'mode': 'pair'}, headers=H).json()['table']
    s = state(a, tid)
    assert s['status'] == 'waiting' and s['invite'] and s['board'] is None
    assert stranger.get(f'/api/tables/{tid}').status_code == 409                              # not seated: refused
    assert stranger.post('/api/join', json={'code': s['invite']}, headers=H).status_code == 409
    assert b.post('/api/join', json={'code': s['invite']}, headers=H).json()['table'] == tid
    sa, sb = state(a, tid), state(b, tid)
    assert sa['me'] == 'S' and sb['me'] == 'N' and sa['status'] == 'playing'
    # Each sees only their own hand during the auction.
    assert sa['board']['hands']['N']['cards'] is None and sb['board']['hands']['S']['cards'] is None
    # Drive the board with both players acting on their turns.
    deadline = time.time() + 60
    while time.time() < deadline:
        moved = False
        for c in (a, b):
            s = state(c, tid)
            check_boundary(s)
            bd = s['board']
            if bd['phase'] == 'done':
                break
            if bd['turn'] and bd['turn']['mine']:
                if bd['turn']['kind'] == 'call':
                    call = '1N' if c is b and '1N' in bd['legal'] and not any(x != 'PASS' for x in bd['calls']) else 'PASS'
                    c.post(f'/api/tables/{tid}/call', json={'call': call}, headers=H)
                else:
                    c.post(f'/api/tables/{tid}/card', json={'card': bd['legal'][0]}, headers=H)
                moved = True
        if state(a, tid)['board']['phase'] == 'done':
            break
        if not moved:
            time.sleep(0.02)
    sa, sb = state(a, tid), state(b, tid)
    assert sa['board']['phase'] == 'done' and sb['board']['result'] == sa['board']['result']
    assert a.get('/api/history').json()['totals']['boards'] == 1 and b.get('/api/history').json()['totals']['boards'] == 1
    bid = a.get('/api/history').json()['boards'][0]['id']
    assert stranger.get(f'/api/boards/{bid}').status_code == 404
